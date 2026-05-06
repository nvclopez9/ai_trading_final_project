import sys
sys.path.insert(0, r"C:\Users\nvclo\Documents\ai_trading_final_project\.venv\Lib\site-packages")

# ---------------------------------------------------------------------------
# Python 3.14 + Pydantic compatibility patch (must run before any langchain
# import triggers langchain.chains.base.Chain class creation).
#
# Root cause: Pydantic's NsResolver.types_namespace includes vars(typ) in the
# locals namespace for annotation evaluation (pydantic/_internal/_namespace_utils.py).
# vars(BaseModel) contains `dict` as a *function* (deprecated alias for
# model_dump()). Python 3.14's annotationlib.ForwardRef.evaluate then calls:
#   eval('dict[str, Any]', globals, locals)
# with locals['dict'] = <method>, which fails with:
#   TypeError: 'function' object is not subscriptable
#
# Fix: wrap pydantic's _eval_type to replace any non-type entry that shadows
# a builtin type in localns with the actual builtin type.
# ---------------------------------------------------------------------------
if sys.version_info >= (3, 14):
    import builtins as _builtins_mod
    import pydantic._internal._typing_extra as _pyd_typing

    _orig_eval_type = _pyd_typing._eval_type

    # Map builtin type names → actual builtin type objects
    _BUILTIN_TYPES: dict = {
        name: obj
        for name in dir(_builtins_mod)
        if isinstance((obj := getattr(_builtins_mod, name)), type)
    }

    def _patched_eval_type(value, globalns, localns, type_params=()):
        """Prevent class methods from shadowing builtin types in localns.

        Specifically fixes BaseModel.dict() (a function) shadowing the builtin
        dict type when pydantic evaluates Optional[dict[str, Any]] annotations
        on langchain.chains.base.Chain under Python 3.14.
        """
        if localns is not None:
            patched = None
            for name, builtin_type in _BUILTIN_TYPES.items():
                try:
                    val = localns[name]
                    if not isinstance(val, type):
                        # Non-type entry shadows a builtin type — fix it
                        if patched is None:
                            patched = dict(localns)
                        patched[name] = builtin_type
                except (KeyError, TypeError):
                    pass
            if patched is not None:
                localns = patched
        return _orig_eval_type(value, globalns, localns, type_params)

    _pyd_typing._eval_type = _patched_eval_type

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
