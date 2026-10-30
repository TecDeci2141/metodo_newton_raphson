# Newton-Raphson Studio

Aplicación web educativa para resolver sistemas no lineales mediante Newton-Raphson multivariable.

## Requisitos
- Python 3.10 o superior
- pip

## Instalación

```bash
# 1. Crear y activar un entorno virtual (recomendado)
python -m venv .venv

# Windows
.venv\Scripts\activate

# Debian / Linux / macOS
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar
python app.py
```

Abre `http://127.0.0.1:5000` en el navegador.

## Tecnologías
- Flask: servidor y API
- SymPy: interpretación simbólica y Jacobiano
- NumPy: cálculo numérico
- OpenPyXL: exportación del libro Excel
- HTML, CSS y JavaScript: interfaz

## Sintaxis de ecuaciones
Usa las variables `x1`, `x2`, ..., `x8`.
- Potencias: `x1**2`
- Multiplicación: `x1*x2`
- Funciones: `sin(x1)`, `cos(x1)`, `exp(x1)`, `log(x1)`, `sqrt(x1)`
- Constantes: `pi`, `E`

El sistema debe tener el mismo número de ecuaciones que incógnitas.

## Estructura

```text
newton_raphson_web/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── css/styles.css
    └── js/app.js
```

## Nota
El cálculo se realiza en el servidor. La exportación vuelve a ejecutar el sistema con los mismos parámetros y genera un Excel con guía, fundamento, sistema/Jacobiano, iteraciones, detalle y solución final.
