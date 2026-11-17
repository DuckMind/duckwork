# pytest must not collect the plugin's own `__init__.py` (it is a Duckwork
# provider module, importable only with the Duckwork runtime on sys.path).
collect_ignore = ["__init__.py"]
