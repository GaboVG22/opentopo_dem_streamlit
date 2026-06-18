# Prompt para continuar: aplicación del eje del cauce principal en KMZ

Quiero crear una aplicación en Streamlit, desplegable en GitHub y Streamlit Cloud, cuyo objetivo sea generar automáticamente el eje del cauce principal de una cuenca y exportarlo en formato KMZ.

Contexto:
Estoy trabajando con delimitación de cuencas a partir de un punto de control ingresado en KMZ/KML. Ya cuento con una aplicación previa para descargar un DEM COP30 en GeoTIFF desde OpenTopography usando la API `/globaldem`. Ahora necesito una aplicación específica para obtener el eje del cauce principal de la cuenca.

Objetivo principal:
La aplicación debe permitir ingresar un punto de control de cuenca en KMZ/KML y un DEM GeoTIFF, procesar hidrológicamente el DEM, delimitar la cuenca aportante y extraer el eje del cauce principal, exportándolo como KMZ.

Requisitos funcionales:

1. Permitir cargar un archivo KMZ/KML con el punto de control o punto de salida de la cuenca.
2. Leer automáticamente latitud, longitud y nombre del punto si existe.
3. Permitir cargar un DEM GeoTIFF, preferentemente COP30 descargado desde OpenTopography.
4. Mostrar la coordenada original del punto.
5. Procesar el DEM hidrológicamente:
   - corregir NoData;
   - rellenar depresiones;
   - resolver flats si corresponde;
   - calcular dirección de flujo;
   - calcular acumulación de flujo.
6. Ajustar automáticamente el punto de control al píxel de mayor acumulación de flujo cercano.
7. Permitir configurar radio de ajuste: 100 m, 250 m, 500 m o 1000 m.
8. Mostrar coordenada original y coordenada ajustada.
9. Delimitar la cuenca aportante al punto ajustado.
10. Extraer la red de drenaje usando umbral de acumulación configurable.
11. Sugerir automáticamente un umbral según tamaño de cuenca.
12. Identificar el cauce principal como la ruta hidráulicamente más representativa desde la salida hasta la cabecera más lejana, priorizando longitud hidráulica y acumulación de flujo.
13. Generar una línea del eje del cauce principal.
14. Permitir suavizado opcional de la línea.
15. Calcular atributos del eje:
    - longitud total en metros;
    - longitud total en kilómetros;
    - cota de cabecera;
    - cota de salida;
    - desnivel total;
    - pendiente media.
16. Generar perfil longitudinal con distancia acumulada y cota.
17. Mostrar mapas con DEM, cuenca, red de drenaje, eje del cauce, punto original y punto ajustado.
18. Exportar KMZ final con estilos:
    - punto original amarillo;
    - punto ajustado rojo;
    - cuenca transparente con borde verde;
    - red secundaria celeste delgada;
    - eje del cauce principal azul grueso.
19. Exportar también GeoJSON del eje, CSV del perfil longitudinal y TXT/JSON con resumen técnico.
20. Manejar errores cuando el KMZ/KML no tenga punto, el DEM no cubra el punto, el punto esté fuera del DEM, no se logre ajuste a drenaje, o no exista red continua.

Compatibilidad:
Debe funcionar en Streamlit Cloud e incluir:

- `app.py`
- `requirements.txt`
- `README.md`
- `.streamlit/config.toml`

Main file path:

```text
app.py
```

Consideraciones técnicas:
Usar librerías compatibles con Streamlit Cloud. Evitar dependencias innecesarias o problemáticas con NumPy reciente. Considerar `rasterio`, `numpy`, `pandas`, `shapely`, `pyproj`, `scipy`, `folium`, `streamlit-folium` y `simplekml`. Si se usa `pysheds`, aplicar compatibilidad si aparece error con `np.in1d`, reemplazando por `np.isin`.

Entrada esperada:

1. KMZ/KML con punto de control.
2. DEM GeoTIFF COP30 u otro DEM válido.

Salida esperada:

1. KMZ con eje del cauce principal.
2. KMZ o GeoJSON de la cuenca.
3. CSV del perfil longitudinal.
4. Resumen técnico descargable.

Ejemplo real:

```text
Latitud : -30.88173168
Longitud: -71.02085661
DEM: COP30 GeoTIFF descargado desde OpenTopography
```

Antes de entregar el ZIP, verificar que `app.py` compile correctamente, que el KMZ tenga geometrías válidas, que la línea del cauce principal esté en WGS84 y que el perfil longitudinal tenga distancia acumulada y cotas.
