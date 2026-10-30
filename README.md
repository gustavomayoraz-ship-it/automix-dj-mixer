<h1 align="center">🎚️ AutoMix</h1>
<p align="center"><b>El DJ que mezcla por vos.</b><br>
Cargás tus canciones, apretás play y AutoMix <b>escucha cada tema, decide cómo empalmarlo con el siguiente y lo mezcla solo</b>,<br>
con el cruce, el bajo y el ritmo bien pegados, como lo haría un DJ con oído.</p>

<p align="center"><b>100 % gratis · para Windows · sin registrarte en ningún lado</b></p>

<p align="center">
  <a href="https://github.com/gustavomayoraz/AutoMix_DJ/releases/latest/download/AutoMix-Setup.exe"><img alt="Descargar AutoMix para Windows" src="https://img.shields.io/badge/%E2%AC%87%EF%B8%8F%20DESCARGAR%20AUTOMIX-Windows-22d3ff?style=for-the-badge"></a>
</p>

<p align="center"><img src="docs/captura.png" alt="AutoMix, mezclador DJ automático de dos decks" width="100%"></p>

> 🎧 **¿Una fiesta, un cumpleaños, una reunión, o simplemente tu música sonando sin cortes?**
> Armás la lista, le das play y te olvidás: los temas se van enganchando uno con otro, parejos, en tempo y sin saltos.

---

## ✨ Lo que lo hace especial

AutoMix no se limita a bajar un tema y subir otro. **Analiza cada par de canciones** (voz, bajo, compases, frases, BPM y tonalidad) y **diseña una mezcla distinta para cada uno**.

### 🤖 Mezcla que se ve y se oye profesional
- **🎯 Cada mezcla es a medida.** El cruce Auto estudia los dos temas y decide cuándo entra el que viene, cómo se va el que sale y en qué compás se pasan el bajo. No hay dos cruces iguales.
- **⏱ Dura exactamente lo que vos elijas.** Ponés 20 segundos y la mezcla dura 20, con pausa incluida. Sin sorpresas.
- **🥁 Graves limpios, sin choque de bombos.** El bombo y el bajo pasan de un tema al otro justo en la línea del compás: nada de empastes ni "golpes dobles".
- **⏸ Pausa en medio del cruce.** Frená la mezcla donde quieras, de 0 a 9 segundos, y seguí. Lo dibujás con una simple línea sobre el gráfico.
- **🌫 Mezcla en el break.** Cuando el tema que suena tiene un hueco (una parada de percusión, un respiro), AutoMix lo detecta y engancha ahí, justo en el mejor momento. Lo regulás con tres deslizadores y ves las líneas en vivo sobre el timeline.
- **⚓ Auto-DJ de punta a punta.** Una marca roja sobre la barra de progreso decide dónde arranca la mezcla (clic derecho para restablecerla). O mezclás vos a mano con la tecla **F2**.
- **🎼 Lo que no pega, no se fuerza.** Si dos temas chocan en tonalidad o en BPM, en vez de un cruce feo hace un fundido elegante, que podés dibujar arrastrando puntos con el mouse.
- **✋ Tu forma de cruce, a tu gusto.** El modo Manual muestra el cruce dibujado en vivo y lo ajustás con deslizadores. Un clic copia el último cruce del Auto para dejarlo fijo. El Auto y el Manual tienen **configuraciones separadas**.
- **⏏ Cerrá la fiesta sin mezclar más.** Un botón deja el deck en espera vacío: el tema que suena termina entero y el reproductor se detiene solo.
- **⚠ Archivos que fallan, no te frenan.** Si un archivo no se puede abrir, se anota y se saltea; después lo revisás cuando quieras.

### 🧠 Entiende tu música
- **BPM y tonalidad de cada tema** (rueda de Camelot), con la lista que se ordena sola mientras analiza: por BPM, por tono, por carpetas, o en cadena armónica para que los temas "encajen".
- **Auto-grilla:** corrige los BPM doble/mitad y centra la grilla de compases sobre los bombos, sin que arrastres nada.
- **Volumen parejo:** el AutoGain empareja el volumen de cada tema al cargarlo.
- **Dos decks sincronizados:** tempo compartido y fase pegada, con estiramiento de tiempo **WSOLA** que cambia la velocidad **sin cambiar el tono**.

### 🎛 Sonido cuidado
- **Ecualizador multibanda inteligente** (graves, medios y agudos): en **automático** se ajusta solo; en **manual** movés la compensación de cada banda, y un botón vuelve a los valores de fábrica. Más controles de golpe a 43 Hz, medios y agudos.
- **Compensación de nivel** mientras suenan los dos temas, y **limitador** que evita que la onda se recorte.
- **🎧 Auriculares con preescucha (PFL):** escuchás cualquiera de los dos decks por otra placa de sonido sin mandarlo a los parlantes.
- **🔁 Loops de 1/4, 1/2, 1 o 2 compases** pegados a la grilla, para el clásico "chiqui-chiqui" mientras entra el otro tema.

### 🎬 Pensado para el directo
- **Timeline en vivo** con la forma de onda de los dos temas, **el nombre de cada uno a la vista**, playhead fijo al centro, marcas de compás y zoom.
- **45 efectos de sonido** (aplausos, ovación, sirenas, risers, impactos, scratch, campanas, láser y más) que se suman encima de la mezcla, con su propio volumen.
- **⏺ Grabá tu mezcla** en MP3 (320 kbps) o WAV sin pérdida, con cierre suave para que no corte en seco.
- **Teclas globales** (F2 mezcla, flechas para el volumen) que funcionan aunque el programa esté en segundo plano.
- **Interfaz que se adapta a tu pantalla:** se escala sola con la ventana y la lista de temas crece cuando la maximizás.

---

## ⬇️ Probalo ahora (menos de 5 minutos)

### Windows, fácil (no necesita Python)
1. **Bajá [`AutoMix-Setup.exe`](https://github.com/gustavomayoraz/AutoMix_DJ/releases/latest/download/AutoMix-Setup.exe)** (descarga directa de la última versión; todas están en [Releases](https://github.com/gustavomayoraz/AutoMix_DJ/releases)).
2. **Doble clic.** Baja solo todo lo necesario (Python 3.14 propio y las librerías, unos 600 MB a 1 GB la primera vez) y abre AutoMix.
3. **Listo:** después se abre desde el acceso directo del Escritorio. Se desinstala desde *Aplicaciones y características*.

> Si Windows muestra "Windows protegió su PC", tocá *Más información* → *Ejecutar de todas formas* (el programa es nuevo y no está firmado).

### Desde el código
    pip install -r requirements.txt
    python AutoMix.py

Requiere Python 3.10+.

---

## 💬 Me ayudás un montón si me contás qué te pareció
AutoMix es **gratis y lo hago por gusto**. Lo único que pido es saber si lo usás y si te gustó:

- ⭐ **Dejale una estrella** al repositorio (arriba a la derecha): así sé que sirve y lo encuentra más gente.
- 🗣 **Contame tu experiencia** (qué te gustó, qué mejorarías, qué falló) en [Issues](https://github.com/gustavomayoraz/AutoMix_DJ/issues): sirve tanto una felicitación como una crítica.

## Datos locales
El programa crea una carpeta `cache/` junto al script (configuración, biblioteca y análisis). No se sube al repositorio.

## Créditos
Desarrollado por Gustavo Mayoraz con la ayuda de [Claude](https://claude.ai) (Anthropic), la herramienta de IA que se usó para programarlo.

Palabras clave: DJ, auto DJ, automix, mezcla automática, crossfade, beatmatching, BPM, mezclador de dos decks, Python, PySide6, librosa.
