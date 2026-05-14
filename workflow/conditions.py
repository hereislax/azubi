"""Sichere Auswertung von Bedingungs-Ausdrücken.

Wird für ``WorkflowDefinition.pre_condition`` und ``WorkflowStep.skip_condition``
verwendet. Erlaubt sind:

- Attribut-Zugriffe: ``initiator.profile.flag``, ``target.duration``
- Vergleichs-Operatoren: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``in``, ``not in``
- Boolesche Operatoren: ``and``, ``or``, ``not``
- Literale: Zahlen, Strings, ``True``, ``False``, ``None``, Tupel/Listen daraus

Nicht erlaubt: Funktions-Aufrufe, Import, Lambdas, Comprehensions, beliebige
Variablen außer den Kontext-Namen.
"""
import ast
from typing import Any


ALLOWED_NAMES = {'initiator', 'target', 'True', 'False', 'None'}

_BOOL_OPS = {ast.And: all, ast.Or: any}
_CMP_OPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


class ConditionError(Exception):
    """Wird geworfen, wenn ein Ausdruck ungültig ist."""


def evaluate(expression: str, *, initiator=None, target=None) -> Any:
    """Wertet einen Bedingungs-Ausdruck im gegebenen Kontext sicher aus.

    Leerer Ausdruck → ``True`` (kein Pre-Condition gesetzt = immer ausführen).
    """
    if not expression or not expression.strip():
        return True

    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError as exc:
        raise ConditionError(f'Syntaxfehler im Ausdruck: {exc}') from exc

    context = {'initiator': initiator, 'target': target,
               'True': True, 'False': False, 'None': None}

    return _eval_node(tree.body, context)


def _eval_node(node, ctx):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id not in ALLOWED_NAMES:
            raise ConditionError(f'Unbekannter Name: {node.id!r}')
        return ctx.get(node.id)

    if isinstance(node, ast.Attribute):
        obj = _eval_node(node.value, ctx)
        if obj is None:
            return None
        # Schutz vor Dunder-Attributen (z.B. __class__, __init__)
        if node.attr.startswith('_'):
            raise ConditionError(f'Privater Attribut-Zugriff verboten: {node.attr}')
        return getattr(obj, node.attr, None)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, ctx)

    if isinstance(node, ast.BoolOp):
        op = _BOOL_OPS.get(type(node.op))
        if op is None:
            raise ConditionError('Unbekannter Bool-Operator')
        return op(_eval_node(v, ctx) for v in node.values)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, ctx)
            cmp_fn = _CMP_OPS.get(type(op))
            if cmp_fn is None:
                raise ConditionError(f'Unbekannter Vergleichsoperator: {type(op).__name__}')
            if not cmp_fn(left, right):
                return False
            left = right
        return True

    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return tuple(_eval_node(e, ctx) for e in node.elts)

    raise ConditionError(f'Nicht erlaubter Ausdrucks-Typ: {type(node).__name__}')


def safe_evaluate(expression: str, *, initiator=None, target=None,
                  default: bool = True) -> bool:
    """Wie ``evaluate``, aber gibt ``default`` bei Fehlern zurück.

    Für den Produktiv-Einsatz: ungültige Bedingungen sollen nicht zu Crash
    führen, sondern in den Default fallen (i.d.R. „Stufe ausführen").
    """
    try:
        result = evaluate(expression, initiator=initiator, target=target)
        return bool(result)
    except ConditionError:
        return default
