from flask import Flask, render_template, request, jsonify, send_file
import io
import re
from datetime import datetime

import numpy as np
import sympy as sp
from sympy import Matrix, lambdify, simplify
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

app = Flask(__name__)

ALLOWED_FUNCTIONS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp,
    "log": sp.log, "sqrt": sp.sqrt, "pi": sp.pi, "E": sp.E,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    " Abs": sp.Abs, "abs": sp.Abs
}
ALLOWED_NAMES = set(ALLOWED_FUNCTIONS) | {"x" + str(i) for i in range(1, 9)}
SAFE_PATTERN = re.compile(r"^[0-9a-zA-Z_+\-*/().,\s\[\]]+$")


def parse_system(equations, n):
    if len(equations) != n:
        raise ValueError("Debes proporcionar exactamente una ecuación por variable.")
    symbols = sp.symbols(f"x1:{n+1}")
    local = {str(s): s for s in symbols}
    local.update(ALLOWED_FUNCTIONS)
    expressions = []
    for i, raw in enumerate(equations):
        expr_text = str(raw).strip()
        if not expr_text:
            raise ValueError(f"La ecuación {i+1} está vacía.")
        if not SAFE_PATTERN.fullmatch(expr_text):
            raise ValueError(f"La ecuación {i+1} contiene caracteres no permitidos.")
        try:
            expr = sp.sympify(expr_text, locals=local, evaluate=True)
            unknown = expr.free_symbols - set(symbols)
            if unknown:
                raise ValueError(f"Variable no permitida: {', '.join(map(str, unknown))}")
            expressions.append(expr)
        except Exception as exc:
            raise ValueError(f"No se pudo interpretar la ecuación {i+1}: {exc}")
    return symbols, Matrix(expressions)


def solve_newton(equations, x0, tol=1e-10, max_iter=50):
    n = len(x0)
    symbols, F = parse_system(equations, n)
    J = simplify(F.jacobian(symbols))
    f_raw = lambdify(symbols, F, modules="numpy")
    j_raw = lambdify(symbols, J, modules="numpy")

    def f_vec(x):
        return np.asarray(f_raw(*x), dtype=float).reshape(-1)

    def j_vec(x):
        return np.asarray(j_raw(*x), dtype=float).reshape(n, n)

    x = np.asarray(x0, dtype=float)
    history = []
    solution = None
    message = ""
    for k in range(max_iter):
        try:
            fx, jx = f_vec(x), j_vec(x)
            if not np.all(np.isfinite(fx)) or not np.all(np.isfinite(jx)):
                raise ValueError("Se obtuvo un valor no finito. Revisa el dominio de las funciones.")
        except Exception as exc:
            message = f"Error al evaluar el sistema en la iteración {k}: {exc}"
            break

        abs_error = float(np.linalg.norm(fx, 2))
        rel_error = float("inf") if not history else float(
            np.linalg.norm(x - history[-1]["x"], 2) / (np.linalg.norm(x, 2) + 1e-14)
        )
        record = {
            "iteration": k, "x": x.copy(), "fx": fx.copy(), "jacobian": jx.copy(),
            "absolute_error": abs_error, "relative_error": rel_error,
            "converged": abs_error < tol, "delta": None, "next_x": None
        }
        if abs_error < tol:
            history.append(record)
            solution = x.copy()
            message = f"Convergencia alcanzada en {k} iteraciones."
            break
        try:
            delta = np.linalg.solve(jx, -fx)
        except np.linalg.LinAlgError:
            history.append(record)
            message = f"El Jacobiano es singular o casi singular en la iteración {k}. Prueba otro punto inicial."
            break
        record["delta"] = delta.copy()
        record["next_x"] = (x + delta).copy()
        history.append(record)
        x = x + delta
    else:
        message = f"No convergió después de {max_iter} iteraciones."

    if not message:
        message = "El cálculo terminó sin solución."
    return {
        "symbols": symbols, "F": F, "J": J, "solution": solution,
        "history": history, "message": message, "converged": solution is not None
    }


def json_safe(result):
    history = []
    for r in result["history"]:
        history.append({
            "iteration": r["iteration"],
            "x": r["x"].tolist(), "fx": r["fx"].tolist(),
            "jacobian": r["jacobian"].tolist(),
            "absolute_error": r["absolute_error"],
            "relative_error": None if not np.isfinite(r["relative_error"]) else r["relative_error"],
            "converged": r["converged"],
            "delta": None if r["delta"] is None else r["delta"].tolist(),
            "next_x": None if r["next_x"] is None else r["next_x"].tolist()
        })
    return {
        "message": result["message"], "converged": result["converged"],
        "solution": None if result["solution"] is None else result["solution"].tolist(),
        "equations": [str(v) for v in result["F"]],
        "jacobian_symbolic": [[str(result["J"][i, j]) for j in range(result["J"].cols)] for i in range(result["J"].rows)],
        "history": history
    }


def build_excel(payload, result):
    wb = Workbook()
    navy = "172554"
    blue = "2563EB"
    pale = "DBEAFE"
    green = "DCFCE7"
    white_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    border = Border(*( [Side(style="thin", color="CBD5E1")] * 4 ))

    # Guide
    ws = wb.active
    ws.title = "0. Guía"
    guide = [
        ["NEWTON-RAPHSON MULTIVARIABLE"],
        ["Guía de uso"],
        ["1. Revisa el sistema y el Jacobiano simbólico."],
        ["2. En cada iteración observa x(k), F(x(k)) y J(x(k))."],
        ["3. Se resuelve J(xk) · Δx = -F(xk)."],
        ["4. Se actualiza x(k+1) = x(k) + Δx."],
        ["5. La convergencia se verifica con ||F(xk)||₂ < tolerancia."],
        ["Advertencia: el método puede divergir o fallar si el Jacobiano es singular."]
    ]
    for row in guide: ws.append(row)
    ws["A1"].font = Font(bold=True, size=16, color=navy)
    ws.column_dimensions["A"].width = 105

    # Theory
    ws = wb.create_sheet("1. Método")
    rows = [
        ["FUNDAMENTO DEL MÉTODO"],
        ["Objetivo", "Encontrar x* tal que F(x*) = 0 para un sistema de n ecuaciones no lineales."],
        ["Jacobiano", "Matriz de derivadas parciales J(x) = [∂Fi/∂xj]."],
        ["Iteración", "J(xk) · Δx = -F(xk); después x(k+1) = xk + Δx."],
        ["Criterio de parada", "||F(xk)||₂ < tolerancia."],
        ["Ventaja", "Convergencia cuadrática cerca de la raíz si se cumplen las condiciones adecuadas."],
        ["Riesgos", "Puede divergir con un punto inicial inadecuado o fallar con Jacobiano singular."]
    ]
    for row in rows: ws.append(row)
    ws["A1"].font = Font(bold=True, size=15, color=navy)
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 110
    for row in ws.iter_rows():
        for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")

    # System
    ws = wb.create_sheet("2. Sistema y Jacobiano")
    ws.append(["SISTEMA Y JACOBIANO"])
    ws.append(["Nombre", payload.get("name", "Sistema del alumno")])
    ws.append(["Tolerancia", payload["tolerance"]])
    ws.append(["Máximo de iteraciones", payload["max_iter"]])
    ws.append([])
    ws.append(["Ecuaciones"])
    for i, eq in enumerate(payload["equations"], 1): ws.append([f"F{i}(x) = 0", eq])
    ws.append([])
    ws.append(["Jacobiano simbólico"])
    for row in result["J"].tolist(): ws.append([str(v) for v in row])
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 50

    # Iterations
    ws = wb.create_sheet("3. Iteraciones")
    n = len(payload["x0"])
    headers = ["Iteración"] + [f"x{i+1}" for i in range(n)] + [f"F{i+1}(x)" for i in range(n)] + ["Error absoluto", "Error relativo", "Convergió"]
    ws.append(headers)
    for c in ws[1]:
        c.font = white_font; c.fill = PatternFill("solid", fgColor=navy); c.alignment = center
    for r in result["history"]:
        row = [r["iteration"]] + r["x"].tolist() + r["fx"].tolist() + [
            r["absolute_error"], None if not np.isfinite(r["relative_error"]) else r["relative_error"],
            "Sí" if r["converged"] else "No"
        ]
        ws.append(row)
        for c in ws[ws.max_row]:
            c.border = border
            if c.column > 1: c.number_format = "0.0000000000"
        if r["converged"]:
            for c in ws[ws.max_row]: c.fill = PatternFill("solid", fgColor=green)
    for col in range(1, len(headers)+1): ws.column_dimensions[get_column_letter(col)].width = 17
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions

    # Details
    ws = wb.create_sheet("4. Detalle por iteración")
    ws.append(["DESGLOSE PASO A PASO"])
    for r in result["history"]:
        ws.append([f"ITERACIÓN k = {r['iteration']}"])
        ws.append(["Vector x(k)"] + r["x"].tolist())
        ws.append(["Residual F(xk)"] + r["fx"].tolist())
        ws.append(["Jacobiano J(xk)"])
        for line in r["jacobian"].tolist(): ws.append([""] + line)
        if r["delta"] is not None:
            ws.append(["Incremento Δx"] + r["delta"].tolist())
            ws.append(["Nuevo punto x(k+1)"] + r["next_x"].tolist())
        ws.append(["Error absoluto", r["absolute_error"]])
        ws.append([])
    ws.column_dimensions["A"].width = 28
    for col in range(2, n+2): ws.column_dimensions[get_column_letter(col)].width = 20

    # Final
    ws = wb.create_sheet("5. Solución final")
    ws.append(["RESULTADO FINAL"])
    ws.append(["Estado", result["message"]])
    if result["solution"] is not None:
        ws.append([])
        ws.append(["Variable", "Valor"])
        for i, value in enumerate(result["solution"], 1): ws.append([f"x{i}*", float(value)])
        final_fx = result["history"][-1]["fx"]
        ws.append([])
        ws.append(["Verificación F(x*)"])
        for i, value in enumerate(final_fx, 1): ws.append([f"F{i}(x*)", float(value)])
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 65
    ws["A1"].font = Font(bold=True, size=15, color=navy)

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = False
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is not None and cell.alignment == Alignment():
                    cell.alignment = Alignment(vertical="center", wrap_text=True)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def validate_payload(data):
    n = int(data.get("n", 0))
    if not 1 <= n <= 8:
        raise ValueError("El número de variables debe estar entre 1 y 8.")
    equations = data.get("equations", [])
    x0 = data.get("x0", [])
    if len(equations) != n or len(x0) != n:
        raise ValueError("El número de ecuaciones y valores iniciales debe coincidir con n.")
    tolerance = float(data.get("tolerance", 1e-10))
    max_iter = int(data.get("max_iter", 50))
    if not 1e-14 <= tolerance <= 1e-2:
        raise ValueError("La tolerancia debe estar entre 1e-14 y 1e-2.")
    if not 1 <= max_iter <= 200:
        raise ValueError("El máximo de iteraciones debe estar entre 1 y 200.")
    x0 = [float(v) for v in x0]
    if not all(np.isfinite(x) for x in x0):
        raise ValueError("El punto inicial debe contener números finitos.")
    return {
        "n": n, "equations": [str(x) for x in equations], "x0": x0,
        "tolerance": tolerance, "max_iter": max_iter,
        "name": str(data.get("name", "Sistema del alumno"))[:120]
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/solve")
def api_solve():
    try:
        payload = validate_payload(request.get_json(force=True))
        result = solve_newton(payload["equations"], payload["x0"], payload["tolerance"], payload["max_iter"])
        return jsonify({"ok": True, "result": json_safe(result)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/export")
def api_export():
    try:
        payload = validate_payload(request.get_json(force=True))
        result = solve_newton(payload["equations"], payload["x0"], payload["tolerance"], payload["max_iter"])
        file = build_excel(payload, result)
        filename = f"newton_raphson_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        return send_file(file, as_attachment=True, download_name=filename,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True)
