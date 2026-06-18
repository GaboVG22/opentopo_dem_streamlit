import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests
import streamlit as st


BASE_URL = "https://portal.opentopography.org/API/globaldem"

DEM_OPTIONS: Dict[str, str] = {
    "COP30": "Copernicus Global DSM 30 m. Recomendado para preparación de DEM de cuencas.",
    "NASADEM": "NASADEM Global DEM. Reprocesamiento de datos SRTM.",
    "SRTMGL1": "SRTM Global 1 arc-second, aprox. 30 m.",
    "SRTMGL3": "SRTM Global 3 arc-second, aprox. 90 m.",
}

DEFAULT_LAT = -30.88173168
DEFAULT_LON = -71.02085661


st.set_page_config(
    page_title="Descarga de DEM COP30",
    page_icon="🗻",
    layout="wide",
)


def _decode_bytes(raw: bytes) -> str:
    """Decode KML text with robust fallbacks."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def read_kml_from_upload(uploaded_file) -> str:
    """Return KML text from a KML or KMZ uploaded file."""
    raw = uploaded_file.read()
    name = uploaded_file.name.lower()

    if name.endswith(".kmz"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
                if not kml_names:
                    raise ValueError("El KMZ no contiene ningún archivo .kml interno.")
                # Prefer doc.kml if it exists; otherwise use the first KML.
                kml_name = next((n for n in kml_names if n.lower().endswith("doc.kml")), kml_names[0])
                return _decode_bytes(zf.read(kml_name))
        except zipfile.BadZipFile as exc:
            raise ValueError("El archivo .kmz no es válido o está dañado.") from exc

    if name.endswith(".kml"):
        return _decode_bytes(raw)

    raise ValueError("Formato no soportado. Cargue un archivo .kml o .kmz.")


def parse_coordinates_text(coords_text: str) -> Tuple[float, float]:
    """Parse KML coordinate text and return lat, lon from first tuple."""
    if not coords_text:
        raise ValueError("La etiqueta <coordinates> está vacía.")

    first_tuple = coords_text.strip().split()[0]
    parts = first_tuple.split(",")
    if len(parts) < 2:
        raise ValueError("Las coordenadas del KML no tienen formato lon,lat[,alt].")

    lon = float(parts[0])
    lat = float(parts[1])
    validate_lat_lon(lat, lon)
    return lat, lon


def extract_first_point_from_kml(kml_text: str) -> Tuple[float, float, str]:
    """Extract the first Point geometry from KML. Returns lat, lon, name."""
    try:
        root = ET.fromstring(kml_text.encode("utf-8"))
    except ET.ParseError:
        # Fallback for imperfect KML exports: regex over Point blocks.
        point_match = re.search(r"<Point[^>]*>.*?<coordinates[^>]*>(.*?)</coordinates>.*?</Point>", kml_text, re.S | re.I)
        if not point_match:
            raise ValueError("No se pudo leer el KML y no se encontró una geometría Point.")
        lat, lon = parse_coordinates_text(point_match.group(1))
        return lat, lon, "Punto de control"

    placemarks = root.findall(".//{*}Placemark")
    for placemark in placemarks:
        point = placemark.find(".//{*}Point")
        if point is None:
            continue
        coords = point.find(".//{*}coordinates")
        if coords is None or not coords.text:
            continue
        lat, lon = parse_coordinates_text(coords.text)
        name_el = placemark.find(".//{*}name")
        name = name_el.text.strip() if name_el is not None and name_el.text else "Punto de control"
        return lat, lon, name

    # Fallback: any Point coordinate, even without Placemark.
    coords = root.find(".//{*}Point/{*}coordinates")
    if coords is not None and coords.text:
        lat, lon = parse_coordinates_text(coords.text)
        return lat, lon, "Punto de control"

    raise ValueError("El KMZ/KML no contiene al menos un punto válido.")


def validate_lat_lon(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise ValueError("La latitud debe estar entre -90 y 90 grados.")
    if not (-180 <= lon <= 180):
        raise ValueError("La longitud debe estar entre -180 y 180 grados.")


def bbox_from_margin(lat: float, lon: float, margin_value: float, margin_unit: str) -> Dict[str, float]:
    """Calculate south, north, west, east from a center point and margin."""
    if margin_value <= 0:
        raise ValueError("El margen debe ser mayor que cero.")

    if margin_unit == "km":
        delta_lat = margin_value / 111.32
        cos_lat = max(math.cos(math.radians(lat)), 0.01)
        delta_lon = margin_value / (111.32 * cos_lat)
    else:
        delta_lat = margin_value
        delta_lon = margin_value

    south = max(-90.0, lat - delta_lat)
    north = min(90.0, lat + delta_lat)
    west = max(-180.0, lon - delta_lon)
    east = min(180.0, lon + delta_lon)

    return {
        "south": round(south, 8),
        "north": round(north, 8),
        "west": round(west, 8),
        "east": round(east, 8),
    }


def bbox_area_km2(bbox: Dict[str, float]) -> float:
    """Approximate area of a geographic bounding box on a sphere."""
    radius_km = 6371.0088
    south = math.radians(bbox["south"])
    north = math.radians(bbox["north"])
    west = math.radians(bbox["west"])
    east = math.radians(bbox["east"])
    area = (radius_km**2) * abs(math.sin(north) - math.sin(south)) * abs(east - west)
    return area


def validate_bbox(bbox: Dict[str, float], area_limit_km2: float) -> None:
    if bbox["south"] >= bbox["north"]:
        raise ValueError("Bounding box inválido: south debe ser menor que north.")
    if bbox["west"] >= bbox["east"]:
        raise ValueError("Bounding box inválido: west debe ser menor que east.")

    area = bbox_area_km2(bbox)
    if area <= 0:
        raise ValueError("El área calculada del bounding box es nula.")
    if area > area_limit_km2:
        raise ValueError(
            f"El área solicitada es excesiva para esta app: {area:,.0f} km². "
            f"Reduzca el margen o aumente el límite técnico si corresponde."
        )


def build_params(dem_type: str, bbox: Dict[str, float], api_key: str) -> Dict[str, str]:
    return {
        "demtype": dem_type,
        "south": str(bbox["south"]),
        "north": str(bbox["north"]),
        "west": str(bbox["west"]),
        "east": str(bbox["east"]),
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }


def build_url(params: Dict[str, str]) -> str:
    return f"{BASE_URL}?{urlencode(params)}"


def mask_api_key(api_key: str) -> str:
    if not api_key:
        return "NO_INGRESADA"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def mask_url(full_url: str, api_key: str) -> str:
    return full_url.replace(api_key, mask_api_key(api_key)) if api_key else full_url.replace("API_Key=", "API_Key=NO_INGRESADA")


def output_filename(dem_type: str, lat: float, lon: float) -> str:
    return f"DEM_{dem_type}_lat_{lat:.4f}_lon_{lon:.4f}.tif"


def metadata_payload(lat: float, lon: float, point_name: str, dem_type: str, bbox: Dict[str, float], masked_download_url: str) -> Dict:
    return {
        "fecha_generacion_utc": datetime.now(timezone.utc).isoformat(),
        "aplicacion": "Descarga de DEM COP30 para punto de control de cuenca",
        "punto_control": {
            "nombre": point_name,
            "latitud": lat,
            "longitud": lon,
            "crs": "WGS84 EPSG:4326",
        },
        "dem_seleccionado": dem_type,
        "bounding_box": bbox,
        "url_descarga_mascarada": masked_download_url,
        "nota_seguridad": "La API Key no se guarda en el repositorio ni se escribe completa en este archivo.",
    }


def metadata_txt(payload: Dict) -> str:
    lines = [
        "DESCARGA DE DEM PARA PUNTO DE CONTROL DE CUENCA",
        "=" * 56,
        f"Fecha generación UTC: {payload['fecha_generacion_utc']}",
        "",
        "Punto de control:",
        f"  Nombre: {payload['punto_control']['nombre']}",
        f"  Latitud: {payload['punto_control']['latitud']}",
        f"  Longitud: {payload['punto_control']['longitud']}",
        f"  CRS: {payload['punto_control']['crs']}",
        "",
        f"DEM seleccionado: {payload['dem_seleccionado']}",
        "",
        "Bounding box:",
        f"  south: {payload['bounding_box']['south']}",
        f"  north: {payload['bounding_box']['north']}",
        f"  west : {payload['bounding_box']['west']}",
        f"  east : {payload['bounding_box']['east']}",
        "",
        "URL de descarga, con API Key oculta:",
        payload["url_descarga_mascarada"],
        "",
        payload["nota_seguridad"],
    ]
    return "\n".join(lines)


def download_dem(params: Dict[str, str]) -> bytes:
    """Download GeoTIFF from OpenTopography without logging or printing API key."""
    try:
        response = requests.get(BASE_URL, params=params, timeout=(10, 180))
    except requests.Timeout as exc:
        raise RuntimeError("Tiempo de espera agotado. Reduzca el área o intente nuevamente.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"No fue posible conectar con OpenTopography: {exc}") from exc

    if response.status_code == 204:
        raise RuntimeError(
            "OpenTopography respondió 204 No Data. Revise que el DEM seleccionado cubra el área "
            "o aumente/modifique el bounding box."
        )
    if response.status_code == 400:
        raise RuntimeError(
            "OpenTopography respondió 400 Bad Request. Revise south/north/west/east, demtype y outputFormat."
        )
    if response.status_code == 401:
        raise RuntimeError(
            "OpenTopography respondió 401 Unauthorized. Revise que la API Key sea correcta y esté activa."
        )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenTopography respondió error HTTP {response.status_code}.")

    content = response.content
    if not content:
        raise RuntimeError("La respuesta de OpenTopography llegó vacía.")

    # TIFF files usually start with II*\x00 or MM\x00*. Some servers return octet-stream.
    lower_start = content[:200].lower()
    content_type = response.headers.get("Content-Type", "").lower()
    looks_like_text_error = lower_start.startswith(b"<html") or lower_start.startswith(b"{") or b"error" in lower_start[:100]
    looks_like_tiff = content.startswith(b"II*\x00") or content.startswith(b"MM\x00*")

    if looks_like_text_error and not looks_like_tiff:
        try:
            message = content.decode("utf-8", errors="ignore")[:500]
        except Exception:
            message = "Respuesta no GeoTIFF desde OpenTopography."
        raise RuntimeError(f"La respuesta no parece ser un GeoTIFF válido: {message}")

    if not looks_like_tiff and "tiff" not in content_type and "octet-stream" not in content_type:
        raise RuntimeError(
            "La descarga terminó, pero el tipo de contenido no parece GeoTIFF. "
            f"Content-Type recibido: {content_type or 'sin informar'}"
        )

    return content


def render_instructions() -> None:
    with st.expander("Instrucciones técnicas y solución de errores", expanded=False):
        st.markdown(
            """
**Dónde obtener la API Key de OpenTopography**  
1. Crear o ingresar a la cuenta en OpenTopography.  
2. Entrar al panel **MyOpenTopo**.  
3. Usar la opción **Get an API Key / Request API Key**.  
4. Pegar la clave en el campo seguro de esta app.

**Qué significa COP30**  
COP30 corresponde al **Copernicus Global DSM 30 m**, un modelo digital de superficie global de aproximadamente 30 m. Para delimitación preliminar de cuencas es una buena base, aunque siempre debe revisarse hidrológicamente antes de usarlo en una modelación final.

**Qué significan south, north, west, east**  
Son los límites geográficos del recorte que se solicitará a OpenTopography en coordenadas WGS84:

- **south**: latitud sur del recorte.
- **north**: latitud norte del recorte.
- **west**: longitud oeste del recorte.
- **east**: longitud este del recorte.

**Errores frecuentes**

- **204 No Data**: el dataset seleccionado no tiene datos para el área o el recorte no intersecta cobertura válida.
- **400 Bad Request**: parámetros incorrectos, por ejemplo `south >= north`, `west >= east`, `demtype` mal escrito o área demasiado grande.
- **401 Unauthorized**: API Key ausente, incorrecta, vencida o no habilitada.

**Recomendación hidráulica**  
Para cuencas pequeñas o medianas conviene comenzar con un margen acotado y luego ampliarlo si el punto de control queda muy cerca del borde del DEM.
            """
        )


st.title("Descarga de DEM COP30 para punto de control de cuenca")
st.caption("Aplicación Streamlit para preparar y descargar un DEM GeoTIFF desde OpenTopography a partir de un punto KMZ/KML.")

with st.sidebar:
    st.header("Parámetros")

    uploaded = st.file_uploader("Cargar punto de control KMZ/KML", type=["kmz", "kml"])
    use_example = st.checkbox("Usar punto de ejemplo real", value=False)

    dem_type = st.selectbox("DEM a descargar", list(DEM_OPTIONS.keys()), index=0)
    st.info(DEM_OPTIONS[dem_type])

    margin_unit_label = st.radio("Tipo de margen", ["grados", "km"], horizontal=True)
    default_margin = 0.35 if margin_unit_label == "grados" else 35.0
    margin_value = st.number_input(
        "Margen desde el punto hacia cada lado",
        min_value=0.0001,
        value=default_margin,
        step=0.05 if margin_unit_label == "grados" else 1.0,
        format="%.4f",
    )

    area_limit = st.number_input(
        "Límite técnico de área solicitada (km²)",
        min_value=1.0,
        max_value=450000.0,
        value=50000.0,
        step=1000.0,
        help="OpenTopography informa un límite de 450.000 km² para datasets de 30 m. Esta app usa un límite menor por seguridad operativa.",
    )

    api_key = st.text_input("API Key de OpenTopography", type="password", help="La clave solo se usa en memoria para construir la solicitud. No se guarda en el repositorio.")

    st.divider()
    st.markdown("**Main file path para Streamlit Cloud:** `app.py`")

point_data: Optional[Tuple[float, float, str]] = None
errors = []

if use_example:
    point_data = (DEFAULT_LAT, DEFAULT_LON, "Punto ejemplo trabajado")
elif uploaded is not None:
    try:
        kml_text = read_kml_from_upload(uploaded)
        point_data = extract_first_point_from_kml(kml_text)
    except Exception as exc:
        errors.append(str(exc))
else:
    st.warning("Cargue un archivo KMZ/KML con un punto de control o active el punto de ejemplo.")

if errors:
    for err in errors:
        st.error(err)

if point_data:
    lat, lon, point_name = point_data
    try:
        bbox = bbox_from_margin(lat, lon, margin_value, margin_unit_label)
        validate_bbox(bbox, area_limit)
        area = bbox_area_km2(bbox)
        params = build_params(dem_type, bbox, api_key or "TU_API_KEY")
        full_url = build_url(params)
        masked = mask_url(full_url, api_key or "TU_API_KEY")
        filename = output_filename(dem_type, lat, lon)

        col1, col2, col3 = st.columns(3)
        col1.metric("Latitud detectada", f"{lat:.8f}")
        col2.metric("Longitud detectada", f"{lon:.8f}")
        col3.metric("Área bbox aprox.", f"{area:,.1f} km²")

        st.subheader("Punto de control detectado")
        st.write(f"**Nombre:** {point_name}")
        st.write(f"**Coordenadas WGS84:** latitud `{lat:.8f}`, longitud `{lon:.8f}`")

        st.subheader("Bounding box calculado para OpenTopography")
        st.json(bbox)

        st.subheader("URL construida con API Key oculta")
        st.code(masked, language="text")

        payload = metadata_payload(lat, lon, point_name, dem_type, bbox, masked)

        download_col1, download_col2 = st.columns(2)
        with download_col1:
            st.download_button(
                "Descargar información JSON",
                data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"info_descarga_{dem_type}_{lat:.4f}_{lon:.4f}.json",
                mime="application/json",
                use_container_width=True,
            )
        with download_col2:
            st.download_button(
                "Descargar información TXT",
                data=metadata_txt(payload).encode("utf-8"),
                file_name=f"info_descarga_{dem_type}_{lat:.4f}_{lon:.4f}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.divider()
        st.subheader("Descarga directa del DEM GeoTIFF")
        st.write(f"Nombre sugerido del archivo: `{filename}`")

        if st.button("Descargar DEM desde OpenTopography", type="primary", use_container_width=True):
            if not api_key.strip():
                st.error("Debe ingresar una API Key de OpenTopography antes de descargar.")
            else:
                real_params = build_params(dem_type, bbox, api_key.strip())
                with st.spinner("Solicitando GeoTIFF a OpenTopography..."):
                    try:
                        dem_bytes = download_dem(real_params)
                        st.session_state["dem_bytes"] = dem_bytes
                        st.session_state["dem_filename"] = filename
                        st.success(f"DEM descargado correctamente en memoria: {len(dem_bytes) / (1024 * 1024):.2f} MB")
                    except RuntimeError as exc:
                        st.error(str(exc))

        if "dem_bytes" in st.session_state:
            st.download_button(
                "Guardar GeoTIFF en mi equipo",
                data=st.session_state["dem_bytes"],
                file_name=st.session_state.get("dem_filename", filename),
                mime="image/tiff",
                use_container_width=True,
            )

    except Exception as exc:
        st.error(str(exc))

render_instructions()

st.divider()
st.caption("La aplicación no delimita cuencas. Solo prepara y descarga el DEM GeoTIFF para uso posterior en análisis hidrológico.")
