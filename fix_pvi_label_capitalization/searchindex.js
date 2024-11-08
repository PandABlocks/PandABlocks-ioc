Search.setIndex({"docnames": ["developer/explanations/decisions", "developer/explanations/decisions/0001-record-architecture-decisions", "developer/explanations/decisions/0002-switched-to-pip-skeleton", "developer/how-to/build-docs", "developer/how-to/contribute", "developer/how-to/lint", "developer/how-to/make-release", "developer/how-to/pin-requirements", "developer/how-to/run-tests", "developer/how-to/static-analysis", "developer/how-to/test-container", "developer/how-to/update-tools", "developer/index", "developer/reference/standards", "developer/tutorials/dev-install", "genindex", "index", "user/explanations/docs-structure", "user/how-to/capture-hdf", "user/how-to/run-container", "user/index", "user/reference/api", "user/tutorials/installation"], "filenames": ["developer/explanations/decisions.rst", "developer/explanations/decisions/0001-record-architecture-decisions.rst", "developer/explanations/decisions/0002-switched-to-pip-skeleton.rst", "developer/how-to/build-docs.rst", "developer/how-to/contribute.rst", "developer/how-to/lint.rst", "developer/how-to/make-release.rst", "developer/how-to/pin-requirements.rst", "developer/how-to/run-tests.rst", "developer/how-to/static-analysis.rst", "developer/how-to/test-container.rst", "developer/how-to/update-tools.rst", "developer/index.rst", "developer/reference/standards.rst", "developer/tutorials/dev-install.rst", "genindex.rst", "index.rst", "user/explanations/docs-structure.rst", "user/how-to/capture-hdf.rst", "user/how-to/run-container.rst", "user/index.rst", "user/reference/api.rst", "user/tutorials/installation.rst"], "titles": ["Architectural Decision Records", "1. Record architecture decisions", "2. Adopt python3-pip-skeleton for project structure", "Build the docs using sphinx", "Contributing to the project", "Run linting using pre-commit", "Make a release", "Pinning Requirements", "Run the tests using pytest", "Run static analysis using mypy", "Container Local Build and Test", "Update the tools", "Developer Guide", "Standards", "Developer install", "API Index", "PandABlocks-ioc", "About the documentation", "Capture data", "Run in a container", "User Guide", "API", "Installation"], "terms": {"we": [0, 1, 2, 4, 7], "major": 0, "adr": [0, 1], "describ": [0, 1], "michael": [0, 1], "nygard": [0, 1], "below": [0, 18], "i": [0, 4, 5, 7, 8, 9, 10, 11, 12, 13, 17, 18, 20, 21, 22], "list": [0, 7, 18], "our": 0, "current": [0, 11, 22], "1": [0, 13, 19], "2": [0, 13, 16, 19], "adopt": 0, "python3": [0, 7, 11, 14, 22], "pip": [0, 7, 11, 14, 16, 22], "skeleton": [0, 7, 11], "project": [0, 1, 3, 7, 8, 10, 11, 12], "structur": [0, 11], "date": [1, 2], "2022": [1, 2], "02": [1, 2], "18": [1, 2], "accept": [1, 2], "need": [1, 7, 17, 22], "made": [1, 7], "thi": [1, 2, 3, 5, 6, 7, 10, 11, 13, 14, 17, 19, 21, 22], "us": [1, 2, 7, 12, 13, 14, 16, 18, 22], "see": [1, 3, 6], "": 1, "articl": 1, "link": [1, 12, 20], "abov": [1, 5], "To": [1, 6, 7, 10, 11, 14, 16, 19], "creat": [1, 6, 7], "new": [1, 4, 6, 14, 20], "copi": [1, 7], "past": 1, "from": [1, 2, 3, 5, 12, 13, 18, 19, 20, 22], "exist": [1, 4, 22], "ones": 1, "should": [2, 4, 7, 22], "follow": [2, 4, 6, 10, 13, 14], "The": [2, 3, 4, 5, 7, 10, 13, 16, 17, 18, 22], "ensur": 2, "consist": 2, "develop": [2, 10, 16], "environ": [2, 4, 7, 14], "packag": [2, 7, 14], "manag": 2, "have": [2, 4, 5, 7, 10, 14, 18], "switch": 2, "modul": [2, 11], "fix": [2, 7, 10], "set": [2, 4, 5, 7, 13], "tool": [2, 12, 13], "can": [2, 3, 5, 7, 8, 9, 10, 14, 18, 22], "pull": [2, 3, 4, 11, 19], "updat": [2, 7, 12], "latest": [2, 7, 11, 19], "techniqu": [2, 11], "As": [2, 13], "mai": [2, 7], "chang": [2, 3, 4, 5, 7, 11, 16], "could": 2, "differ": [2, 7, 17, 19], "lint": [2, 12, 13, 14], "format": [2, 13], "venv": [2, 14, 22], "setup": [2, 11, 14], "ci": [2, 10], "cd": [2, 10, 14], "you": [3, 4, 5, 6, 7, 8, 9, 10, 14, 22], "base": 3, "directori": [3, 13, 16, 18], "run": [3, 4, 10, 11, 12, 13, 14, 16, 20], "tox": [3, 5, 8, 9, 10, 14], "e": [3, 5, 7, 8, 9, 14], "static": [3, 12, 13, 14], "which": [3, 10, 11, 14], "includ": [3, 20], "api": [3, 13, 20], "docstr": [3, 13], "code": [3, 5, 16], "document": [3, 4, 12, 20], "standard": [3, 4, 12], "built": [3, 19], "html": 3, "open": [3, 14], "local": [3, 12, 14], "web": [3, 16], "brows": 3, "firefox": 3, "index": [3, 20], "also": [3, 4, 5, 8, 12, 20, 22], "an": [3, 5, 7, 11], "process": [3, 13], "watch": 3, "your": [3, 4, 5, 7, 10], "rebuild": 3, "whenev": 3, "reload": 3, "ani": [3, 4, 5, 7, 10, 11, 22], "browser": 3, "page": [3, 6, 7, 13], "view": [3, 16, 18], "localhost": 3, "http": [3, 6, 11, 16, 22], "8000": 3, "If": [3, 4, 5, 10, 22], "ar": [3, 4, 7, 13, 17, 18, 19], "make": [3, 4, 12], "sourc": [3, 9, 14, 16, 22], "too": 3, "tell": [3, 5], "src": 3, "issu": [4, 7, 9], "most": [4, 17], "welcom": 4, "all": [4, 5, 7, 10, 16], "request": [4, 11], "handl": [4, 5], "through": [4, 14], "github": [4, 6, 11, 14, 16, 19, 22], "pleas": [4, 6, 13], "check": [4, 5, 8, 9, 10, 11, 13, 14], "befor": 4, "file": [4, 5, 9, 18], "one": [4, 7, 17, 18], "great": 4, "idea": [4, 7], "involv": 4, "big": 4, "ticket": 4, "want": 4, "sure": 4, "don": 4, "t": [4, 10, 17], "spend": 4, "time": [4, 5, 7], "someth": [4, 11], "might": 4, "fit": 4, "scope": 4, "while": 4, "100": 4, "doe": 4, "librari": [4, 7, 20], "bug": 4, "free": 4, "significantli": 4, "reduc": 4, "number": [4, 6, 7, 18, 19, 21], "easili": 4, "caught": 4, "remain": 4, "same": [4, 6, 7], "improv": [4, 17], "contain": [4, 7, 12, 13, 14, 16, 20], "inform": [4, 17], "up": [4, 12, 16], "test": [4, 7, 12], "what": 4, "black": [5, 13], "flake8": [5, 13], "isort": [5, 13], "under": [5, 14], "command": [5, 10], "Or": 5, "instal": [5, 7, 10, 12, 16, 19, 20], "hook": 5, "each": [5, 7], "do": [5, 7, 9, 10], "git": [5, 11, 14, 22], "just": 5, "It": [5, 7, 8, 9, 22], "possibl": [5, 7], "automat": 5, "enabl": 5, "clone": 5, "repositori": [5, 7, 13], "result": 5, "being": 5, "everi": [5, 7], "repo": [5, 7], "user": [5, 16], "now": [5, 14, 22], "report": [5, 8], "reformat": 5, "likewis": 5, "get": [5, 6, 7, 12, 14, 19], "those": 5, "manual": 5, "json": 5, "formatt": 5, "well": 5, "save": 5, "highlight": [5, 9], "editor": 5, "window": 5, "checklist": 6, "choos": [6, 14], "pep440": 6, "compliant": 6, "pep": 6, "python": [6, 7, 11, 14, 16], "org": 6, "0440": 6, "go": [6, 7], "draft": 6, "click": [6, 7, 14], "tag": 6, "suppli": 6, "chose": 6, "gener": [6, 11, 16], "note": [6, 20], "review": 6, "edit": 6, "titl": [6, 13], "publish": [6, 7], "push": [6, 7], "main": 6, "branch": 6, "ha": [6, 7, 11, 18, 22], "effect": 6, "except": 6, "option": 6, "By": 7, "design": 7, "onli": 7, "defin": [7, 13], "place": 7, "tabl": 7, "pyproject": 7, "toml": 7, "In": [7, 10], "version": [7, 11, 19, 21], "some": 7, "For": [7, 13], "best": [7, 10], "leav": 7, "minimum": 7, "so": [7, 14, 22], "widest": 7, "rang": 7, "applic": [7, 10], "when": [7, 14], "build": [7, 12, 13], "compat": 7, "avail": [7, 10, 16, 19], "after": 7, "approach": [7, 17], "mean": [7, 11], "futur": 7, "break": 7, "becaus": [7, 10], "releas": [7, 12, 16, 19, 20, 22], "correct": 7, "wai": [7, 20], "work": [7, 20], "out": 7, "resolv": 7, "problem": [7, 10], "howev": 7, "quit": 7, "hard": 7, "consum": 7, "simpli": 7, "try": 7, "minor": 7, "reason": 7, "provid": [7, 11], "mechan": 7, "previou": 7, "success": 7, "quick": 7, "guarante": 7, "asset": 7, "exampl": [7, 10, 13], "take": [7, 14], "look": [7, 8], "cli": [7, 10], "here": [7, 20], "diamondlightsourc": [7, 11], "There": [7, 17], "txt": 7, "show": 7, "virtual": 7, "multipl": [7, 11], "freez": 7, "full": 7, "sub": 7, "download": 7, "them": [7, 8, 9], "ran": 7, "lowest": 7, "more": [7, 11, 17, 20], "like": [7, 8], "matrix": 7, "ubuntu": 7, "3": [7, 13, 14, 22], "8": [7, 14, 22], "lockfil": 7, "root": [7, 10], "renam": 7, "commit": [7, 12, 13, 14], "pass": [7, 10], "exactli": 7, "onc": [7, 18], "been": [7, 18, 22], "good": [7, 17], "back": [7, 16], "unlock": 7, "earli": 7, "indic": [7, 11], "incom": 7, "restor": 7, "done": [8, 9], "find": 8, "function": [8, 13, 17], "error": 8, "coverag": 8, "commandlin": [8, 22], "cov": 8, "xml": 8, "type": [9, 13, 14, 22], "definit": 9, "without": 9, "potenti": 9, "where": [9, 11], "match": 9, "runtim": 10, "via": 10, "p": [10, 14], "verifi": 10, "docker": [10, 19], "fail": 10, "would": 10, "requir": [10, 12, 14, 17, 22], "podman": 10, "workstat": 10, "interchang": 10, "depend": [10, 19, 22], "call": [10, 17], "help": [10, 17], "other": 10, "line": [10, 13], "paramet": 10, "instead": 10, "merg": 11, "keep": [11, 18], "sync": 11, "between": 11, "rebas": 11, "fals": 11, "com": [11, 14, 22], "conflict": 11, "area": 11, "close": 11, "detail": 11, "split": [12, 16, 20], "four": [12, 17, 20], "categori": [12, 20], "access": [12, 20], "side": [12, 20], "bar": [12, 20], "contribut": [12, 16], "doc": [12, 13, 14], "sphinx": [12, 13, 14], "pytest": [12, 14], "analysi": [12, 13, 14], "mypi": [12, 13, 14], "pre": [12, 13, 14, 19], "pin": 12, "practic": [12, 20], "step": [12, 14, 20], "dai": 12, "dev": [12, 14], "task": 12, "architectur": 12, "decis": 12, "record": 12, "why": [12, 20], "technic": [12, 17, 20], "materi": [12, 20], "conform": 13, "style": 13, "import": 13, "order": [13, 17], "how": [13, 17], "guid": [13, 16, 17], "napoleon": 13, "extens": 13, "googl": 13, "consid": 13, "hint": 13, "signatur": 13, "def": 13, "func": 13, "arg1": 13, "str": [13, 21], "arg2": 13, "int": 13, "bool": 13, "summari": 13, "extend": 13, "descript": 13, "arg": 13, "return": 13, "valu": [13, 16], "true": 13, "extract": 13, "underlin": 13, "convent": 13, "headl": 13, "head": 13, "These": [14, 18], "instruct": 14, "minim": 14, "first": 14, "pandablock": [14, 19, 22], "ioc": [14, 19, 22], "either": 14, "host": [14, 16], "machin": 14, "later": [14, 22], "vscode": 14, "virtualenv": 14, "m": [14, 16, 22], "bin": [14, 22], "activ": [14, 22], "devcontain": 14, "reopen": 14, "prompt": 14, "termin": [14, 22], "graph": 14, "tree": 14, "pipdeptre": 14, "parallel": 14, "A": 16, "softioc": 16, "control": 16, "fpga": 16, "pypi": 16, "io": [16, 19], "pandabox": 16, "pv": [16, 18], "prefix": 16, "screen": [16, 18], "dir": 16, "output": 16, "bobfil": 16, "clear": 16, "shown": 16, "client": [16, 18], "caget": 16, "panda": [16, 18], "calc1": 16, "inpa": 16, "zero": 16, "On": 16, "start": [16, 20], "pvi": 16, "phoebu": 16, "section": 16, "grand": 17, "unifi": 17, "theori": 17, "david": 17, "la": 17, "secret": 17, "understood": 17, "write": [17, 18], "softwar": [17, 22], "isn": 17, "thing": 17, "thei": 17, "tutori": 17, "refer": [17, 21], "explan": 17, "repres": 17, "purpos": 17, "creation": 17, "understand": 17, "implic": 17, "often": 17, "immens": 17, "topic": 17, "name": 18, "chosen": 18, "hdfdirectori": 18, "hdffilenam": 18, "numcaptur": 18, "frame": 18, "written": 18, "numreceiv": 18, "receiv": 18, "flushperiod": 18, "frequenc": 18, "flush": 18, "begin": 18, "capturemod": 18, "three": 18, "soon": 18, "stop": 18, "disarm": 18, "buffer": 18, "finish": 18, "disk": 18, "wait": 18, "arm": 18, "again": 18, "continu": 18, "its": [19, 22], "alreadi": 19, "registri": 19, "ghcr": 19, "append": 19, "end": 19, "0": 19, "typic": 20, "usag": 20, "captur": 20, "data": 20, "experienc": 20, "about": 20, "intern": 21, "__version__": 21, "calcul": 21, "pypa": 21, "setuptools_scm": 21, "recommend": 22, "interfer": 22, "path": 22, "featur": 22, "interfac": 22}, "objects": {"": [[21, 0, 0, "-", "pandablocks_ioc"]], "pandablocks_ioc.pandablocks_ioc": [[21, 1, 1, "", "__version__"]]}, "objtypes": {"0": "py:module", "1": "py:data"}, "objnames": {"0": ["py", "module", "Python module"], "1": ["py", "data", "Python data"]}, "titleterms": {"architectur": [0, 1], "decis": [0, 1, 2], "record": [0, 1], "1": 1, "statu": [1, 2], "context": [1, 2], "consequ": [1, 2], "2": 2, "adopt": 2, "python3": 2, "pip": 2, "skeleton": 2, "project": [2, 4], "structur": [2, 16], "build": [3, 10, 14], "doc": 3, "us": [3, 5, 8, 9], "sphinx": 3, "autobuild": 3, "contribut": 4, "code": [4, 13], "coverag": 4, "develop": [4, 12, 14], "guid": [4, 12, 20], "run": [5, 8, 9, 19], "lint": 5, "pre": 5, "commit": 5, "fix": 5, "issu": 5, "vscode": 5, "support": 5, "make": 6, "releas": 6, "pin": 7, "requir": 7, "introduct": 7, "find": 7, "lock": 7, "file": 7, "appli": 7, "remov": 7, "depend": [7, 14], "from": 7, "ci": 7, "test": [8, 10, 14], "pytest": 8, "static": 9, "analysi": 9, "mypi": 9, "contain": [10, 19], "local": 10, "updat": 11, "tool": 11, "tutori": [12, 20], "how": [12, 16, 20], "explan": [12, 20], "refer": [12, 20], "standard": 13, "document": [13, 16, 17], "instal": [14, 22], "clone": 14, "repositori": 14, "see": 14, "what": 14, "wa": 14, "api": [15, 21], "index": 15, "pandablock": 16, "ioc": 16, "i": 16, "about": 17, "captur": 18, "data": 18, "first": 18, "n": 18, "mode": 18, "last": 18, "forev": 18, "start": 19, "user": 20, "pandablocks_ioc": 21, "check": 22, "your": 22, "version": 22, "python": 22, "creat": 22, "virtual": 22, "environ": 22, "librari": 22}, "envversion": {"sphinx.domains.c": 3, "sphinx.domains.changeset": 1, "sphinx.domains.citation": 1, "sphinx.domains.cpp": 9, "sphinx.domains.index": 1, "sphinx.domains.javascript": 3, "sphinx.domains.math": 2, "sphinx.domains.python": 4, "sphinx.domains.rst": 2, "sphinx.domains.std": 2, "sphinx.ext.intersphinx": 1, "sphinx.ext.viewcode": 1, "sphinx": 60}, "alltitles": {"Architectural Decision Records": [[0, "architectural-decision-records"]], "1. Record architecture decisions": [[1, "record-architecture-decisions"]], "Status": [[1, "status"], [2, "status"]], "Context": [[1, "context"], [2, "context"]], "Decision": [[1, "decision"], [2, "decision"]], "Consequences": [[1, "consequences"], [2, "consequences"]], "2. Adopt python3-pip-skeleton for project structure": [[2, "adopt-python3-pip-skeleton-for-project-structure"]], "Build the docs using sphinx": [[3, "build-the-docs-using-sphinx"]], "Autobuild": [[3, "autobuild"]], "Contributing to the project": [[4, "contributing-to-the-project"]], "Code coverage": [[4, "code-coverage"]], "Developer guide": [[4, "developer-guide"]], "Run linting using pre-commit": [[5, "run-linting-using-pre-commit"]], "Running pre-commit": [[5, "running-pre-commit"]], "Fixing issues": [[5, "fixing-issues"]], "VSCode support": [[5, "vscode-support"]], "Make a release": [[6, "make-a-release"]], "Pinning Requirements": [[7, "pinning-requirements"]], "Introduction": [[7, "introduction"]], "Finding the lock files": [[7, "finding-the-lock-files"]], "Applying the lock file": [[7, "applying-the-lock-file"]], "Removing dependency locking from CI": [[7, "removing-dependency-locking-from-ci"]], "Run the tests using pytest": [[8, "run-the-tests-using-pytest"]], "Run static analysis using mypy": [[9, "run-static-analysis-using-mypy"]], "Container Local Build and Test": [[10, "container-local-build-and-test"]], "Update the tools": [[11, "update-the-tools"]], "Developer Guide": [[12, "developer-guide"]], "Tutorials": [[12, null], [20, null]], "How-to Guides": [[12, null], [20, null]], "Explanations": [[12, null], [20, null]], "Reference": [[12, null], [20, null]], "Standards": [[13, "standards"]], "Code Standards": [[13, "code-standards"]], "Documentation Standards": [[13, "documentation-standards"]], "Developer install": [[14, "developer-install"]], "Clone the repository": [[14, "clone-the-repository"]], "Install dependencies": [[14, "install-dependencies"]], "See what was installed": [[14, "see-what-was-installed"]], "Build and test": [[14, "build-and-test"]], "API Index": [[15, "api-index"]], "PandABlocks-ioc": [[16, "pandablocks-ioc"]], "How the documentation is structured": [[16, "how-the-documentation-is-structured"]], "About the documentation": [[17, "about-the-documentation"]], "Capture data": [[18, "capture-data"]], "First N mode": [[18, "first-n-mode"]], "Last N mode": [[18, "last-n-mode"]], "Forever mode": [[18, "forever-mode"]], "Run in a container": [[19, "run-in-a-container"]], "Starting the container": [[19, "starting-the-container"]], "User Guide": [[20, "user-guide"]], "API": [[21, "module-pandablocks_ioc"]], "pandablocks_ioc": [[21, "pandablocks-ioc"]], "Installation": [[22, "installation"]], "Check your version of python": [[22, "check-your-version-of-python"]], "Create a virtual environment": [[22, "create-a-virtual-environment"]], "Installing the library": [[22, "installing-the-library"]]}, "indexentries": {"module": [[21, "module-pandablocks_ioc"]], "pandablocks_ioc": [[21, "module-pandablocks_ioc"]], "pandablocks_ioc.__version__ (in module pandablocks_ioc)": [[21, "pandablocks_ioc.pandablocks_ioc.__version__"]]}})