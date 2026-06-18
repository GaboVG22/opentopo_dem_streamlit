# Descarga de DEM COP30 para punto de control de cuenca

Aplicación en Streamlit para leer un punto de control desde un archivo **KMZ/KML**, calcular automáticamente un **bounding box** y descargar un DEM en formato **GeoTIFF** desde la API `globaldem` de OpenTopography.

## Objetivo

La app **no delimita la cuenca**. Su objetivo es preparar y facilitar la descarga de un DEM GeoTIFF para que luego pueda usarse en otra aplicación de delimitación de cuencas, cálculo de superficie, curvas de nivel y exportación KMZ.

## Funciones principales

- Carga de punto de control en `KMZ` o `KML`.
- Lectura automática de latitud y longitud WGS84.
- Selección del DEM:
  - `COP30` por defecto.
  - `NASADEM`.
  - `SRTMGL1`.
  - `SRTMGL3`.
- Ingreso de margen en grados o kilómetros.
- Cálculo automático de:
  - `south`
  - `north`
  - `west`
  - `east`
- Generación de URL para OpenTopography:

```text
https://portal.opentopography.org/API/globaldem?demtype=COP30&south=...&north=...&west=...&east=...&outputFormat=GTiff&API_Key=...
```

- Campo seguro tipo password para la API Key.
- URL visible con API Key parcialmente oculta.
- Descarga directa del GeoTIFF desde la app.
- Descarga de información técnica en `JSON` y `TXT`.
- Validaciones de geometría, área, API Key y errores HTTP frecuentes.

## Archivos del proyecto

```text
.
├── app.py
├── requirements.txt
├── README.md
└── .streamlit
    └── config.toml
```

## Main file path para Streamlit Cloud

```text
app.py
```

## Instalación local

Crear un entorno virtual e instalar dependencias:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue en GitHub y Streamlit Cloud

1. Crear un repositorio en GitHub.
2. Subir todos los archivos del proyecto.
3. Ingresar a Streamlit Cloud.
4. Seleccionar el repositorio.
5. Indicar:

```text
Main file path: app.py
```

6. Desplegar.

## API Key de OpenTopography

La API Key no debe guardarse en GitHub ni escribirse en el código. La app solicita la clave mediante un campo tipo password y la usa solo en memoria para realizar la solicitud HTTP.

Para obtenerla:

1. Crear cuenta o iniciar sesión en OpenTopography.
2. Ir a **MyOpenTopo Dashboard**.
3. Seleccionar **Get an API Key** o **Request API Key**.
4. Copiar la clave y pegarla en la app.

## Ejemplo real trabajado

Punto de control:

```text
Latitud : -30.88173168
Longitud: -71.02085661
```

Bounding box de prueba:

```text
south = -31.20
north = -30.55
west  = -71.40
east  = -70.70
```

URL tipo:

```text
https://portal.opentopography.org/API/globaldem?demtype=COP30&south=-31.20&north=-30.55&west=-71.40&east=-70.70&outputFormat=GTiff&API_Key=TU_API_KEY
```

## Errores frecuentes

### 204 No Data

El DEM seleccionado no tiene datos para el área solicitada o el bounding box no intersecta cobertura válida. Revise el área o pruebe otro DEM.

### 400 Bad Request

Los parámetros enviados no son válidos. Revise que:

- `south < north`
- `west < east`
- `demtype` esté correctamente escrito
- El área solicitada no sea excesiva

### 401 Unauthorized

La API Key es incorrecta, está vacía, vencida o no se encuentra habilitada.

## Notas técnicas

- La descarga usa `requests.get()` con HTTPS.
- La API Key no se imprime completa ni se guarda en archivos de salida.
- El archivo GeoTIFF descargado se entrega con nombre ordenado, por ejemplo:

```text
DEM_COP30_lat_-30.8817_lon_-71.0209.tif
```

- El cálculo de margen en kilómetros usa una aproximación geográfica suficiente para preparar recortes DEM. Para análisis geodésicos más estrictos, se recomienda reproyectar posteriormente en UTM.
