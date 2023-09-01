Search.setIndex({"docnames": ["developer/explanations/decisions", "developer/explanations/decisions/0001-record-architecture-decisions", "developer/explanations/decisions/0002-switched-to-pip-skeleton", "developer/how-to/build-docs", "developer/how-to/contribute", "developer/how-to/lint", "developer/how-to/make-release", "developer/how-to/pin-requirements", "developer/how-to/run-tests", "developer/how-to/static-analysis", "developer/how-to/test-container", "developer/how-to/update-tools", "developer/index", "developer/reference/standards", "developer/tutorials/dev-install", "genindex", "index", "user/explanations/docs-structure", "user/how-to/run-container", "user/index", "user/reference/api", "user/tutorials/installation"], "filenames": ["developer/explanations/decisions.rst", "developer/explanations/decisions/0001-record-architecture-decisions.rst", "developer/explanations/decisions/0002-switched-to-pip-skeleton.rst", "developer/how-to/build-docs.rst", "developer/how-to/contribute.rst", "developer/how-to/lint.rst", "developer/how-to/make-release.rst", "developer/how-to/pin-requirements.rst", "developer/how-to/run-tests.rst", "developer/how-to/static-analysis.rst", "developer/how-to/test-container.rst", "developer/how-to/update-tools.rst", "developer/index.rst", "developer/reference/standards.rst", "developer/tutorials/dev-install.rst", "genindex.rst", "index.rst", "user/explanations/docs-structure.rst", "user/how-to/run-container.rst", "user/index.rst", "user/reference/api.rst", "user/tutorials/installation.rst"], "titles": ["Architectural Decision Records", "1. Record architecture decisions", "2. Adopt python3-pip-skeleton for project structure", "Build the docs using sphinx", "Contributing to the project", "Run linting using pre-commit", "Make a release", "Pinning Requirements", "Run the tests using pytest", "Run static analysis using mypy", "Container Local Build and Test", "Update the tools", "Developer Guide", "Standards", "Developer install", "API Index", "PandABlocks-ioc", "About the documentation", "Run in a container", "User Guide", "API", "Installation"], "terms": {"we": [0, 1, 2, 4, 7], "major": 0, "adr": [0, 1], "describ": [0, 1, 16], "michael": [0, 1], "nygard": [0, 1], "below": 0, "i": [0, 4, 5, 7, 8, 9, 10, 11, 12, 13, 17, 19, 20, 21], "list": [0, 7], "our": 0, "current": [0, 11, 21], "1": [0, 13], "2": [0, 13, 16], "adopt": [0, 16], "python3": [0, 7, 11, 14, 16, 21], "pip": [0, 7, 11, 14, 16, 21], "skeleton": [0, 7, 11, 16], "project": [0, 1, 3, 7, 8, 10, 11, 12, 16], "structur": [0, 11], "date": [1, 2], "2022": [1, 2], "02": [1, 2], "18": [1, 2], "accept": [1, 2], "need": [1, 7, 17, 21], "made": [1, 7], "thi": [1, 2, 3, 5, 6, 7, 10, 11, 13, 14, 16, 17, 20, 21], "us": [1, 2, 7, 12, 13, 14, 16, 18, 21], "see": [1, 3, 6, 16], "": 1, "articl": 1, "link": [1, 12, 19], "abov": [1, 5], "To": [1, 6, 7, 10, 11, 14, 18], "creat": [1, 6, 7], "new": [1, 4, 6, 14, 19], "copi": [1, 7], "past": 1, "from": [1, 2, 3, 5, 12, 13, 16, 18, 19, 21], "exist": [1, 4, 21], "ones": 1, "should": [2, 4, 7, 16, 21], "follow": [2, 4, 6, 10, 13, 14], "The": [2, 3, 4, 5, 7, 10, 13, 16, 17, 21], "ensur": 2, "consist": 2, "develop": [2, 10, 16], "environ": [2, 4, 7, 14], "packag": [2, 7, 14], "manag": 2, "have": [2, 4, 5, 7, 10, 14], "switch": 2, "modul": [2, 11, 16], "fix": [2, 7, 10], "set": [2, 4, 5, 7, 13], "tool": [2, 12, 13, 16], "can": [2, 3, 4, 5, 7, 8, 9, 10, 14, 21], "pull": [2, 3, 4, 11, 18], "updat": [2, 7, 12], "latest": [2, 7, 11], "techniqu": [2, 11], "As": [2, 13], "mai": [2, 7], "chang": [2, 3, 4, 5, 7, 11, 16], "could": 2, "differ": [2, 7, 17], "lint": [2, 12, 13, 14], "format": [2, 13], "venv": [2, 14, 21], "setup": [2, 11, 14], "ci": [2, 10], "cd": [2, 10, 14], "you": [3, 4, 5, 6, 7, 8, 9, 10, 14, 16, 21], "base": 3, "directori": [3, 13], "run": [3, 4, 10, 11, 12, 13, 14, 19], "tox": [3, 5, 8, 9, 10, 14], "e": [3, 5, 7, 8, 9, 14], "static": [3, 12, 13, 14], "which": [3, 10, 11, 14], "includ": [3, 19], "api": [3, 13, 19], "docstr": [3, 13], "code": [3, 5, 16], "document": [3, 4, 12, 19], "standard": [3, 4, 12], "built": [3, 18], "html": 3, "open": [3, 4, 14], "local": [3, 12, 14], "web": 3, "brows": 3, "firefox": 3, "index": [3, 19], "also": [3, 4, 5, 8, 12, 19, 21], "an": [3, 5, 7, 11], "process": [3, 13], "watch": 3, "your": [3, 4, 5, 7, 10, 16], "rebuild": 3, "whenev": 3, "reload": 3, "ani": [3, 4, 5, 7, 10, 11, 21], "browser": 3, "page": [3, 6, 7, 13], "view": 3, "localhost": 3, "http": [3, 6, 11, 16, 21], "8000": 3, "If": [3, 4, 5, 10, 16, 21], "ar": [3, 4, 7, 13, 17, 18], "make": [3, 4, 12], "sourc": [3, 9, 14, 16, 21], "too": 3, "tell": [3, 5], "src": 3, "most": [4, 17], "welcom": 4, "all": [4, 5, 7, 10], "request": [4, 11], "handl": [4, 5], "through": [4, 14], "github": [4, 6, 11, 14, 16, 18, 21], "pleas": [4, 6, 13], "check": [4, 5, 8, 9, 10, 11, 13, 14], "befor": 4, "file": [4, 5, 9], "one": [4, 7, 17], "great": 4, "idea": [4, 7], "involv": 4, "big": 4, "ticket": 4, "want": 4, "sure": 4, "don": 4, "t": [4, 10, 17], "spend": 4, "time": [4, 5, 7], "someth": [4, 11], "might": [4, 16], "fit": 4, "scope": 4, "offer": 4, "place": [4, 7], "ask": 4, "question": 4, "share": 4, "end": 4, "obviou": 4, "when": [4, 7, 14], "close": [4, 11], "rais": 4, "instead": [4, 10, 18], "while": 4, "100": 4, "doe": [4, 16], "librari": [4, 7, 16, 19], "bug": 4, "free": 4, "significantli": 4, "reduc": 4, "number": [4, 6, 7, 18, 20], "easili": 4, "caught": 4, "remain": 4, "same": [4, 6, 7], "improv": [4, 17], "contain": [4, 7, 12, 13, 14, 16, 19], "inform": [4, 17], "up": [4, 12], "test": [4, 7, 12], "what": [4, 16], "black": [5, 13], "flake8": [5, 13], "isort": [5, 13], "under": [5, 14], "command": [5, 10, 16], "Or": [5, 16], "instal": [5, 7, 10, 12, 16, 18, 19], "hook": 5, "each": [5, 7], "do": [5, 7, 9, 10], "git": [5, 11, 14, 21], "just": 5, "It": [5, 7, 8, 9, 21], "possibl": [5, 7], "automat": 5, "enabl": 5, "clone": 5, "repositori": [5, 7, 13], "result": 5, "being": 5, "everi": [5, 7], "repo": [5, 7], "user": [5, 16], "now": [5, 14, 21], "report": [5, 8], "reformat": 5, "likewis": 5, "get": [5, 6, 7, 12, 14, 18], "those": 5, "manual": 5, "json": 5, "formatt": 5, "well": 5, "save": 5, "highlight": [5, 9], "editor": 5, "window": 5, "checklist": 6, "choos": [6, 14], "pep440": 6, "compliant": 6, "pep": 6, "python": [6, 7, 11, 14, 16], "org": 6, "0440": 6, "go": [6, 7], "draft": 6, "click": [6, 7, 14], "tag": 6, "suppli": 6, "chose": 6, "gener": [6, 11], "note": [6, 19], "review": 6, "edit": 6, "titl": [6, 13], "publish": [6, 7], "push": [6, 7], "main": [6, 18], "branch": 6, "ha": [6, 7, 11, 21], "effect": 6, "except": 6, "option": 6, "By": 7, "design": 7, "onli": [7, 16], "defin": [7, 13], "tabl": 7, "pyproject": 7, "toml": 7, "In": [7, 10], "version": [7, 11, 16, 18, 20], "some": [7, 16], "For": [7, 13, 16], "best": [7, 10], "leav": 7, "minimum": 7, "so": [7, 14, 21], "widest": 7, "rang": 7, "applic": [7, 10], "build": [7, 12, 13], "compat": 7, "avail": [7, 10, 18], "after": 7, "approach": [7, 17], "mean": [7, 11], "futur": 7, "break": 7, "becaus": [7, 10], "releas": [7, 12, 16, 18, 19, 21], "correct": 7, "wai": [7, 19], "issu": [7, 9], "work": [7, 19], "out": 7, "resolv": 7, "problem": [7, 10], "howev": 7, "quit": 7, "hard": 7, "consum": 7, "simpli": 7, "try": 7, "minor": 7, "reason": 7, "provid": [7, 11], "mechan": 7, "previou": 7, "success": 7, "quick": 7, "guarante": 7, "asset": 7, "exampl": [7, 10, 13, 16], "take": [7, 14], "look": [7, 8], "cli": [7, 10, 16], "here": [7, 16, 19], "diamondlightsourc": [7, 11, 16], "There": [7, 17], "txt": 7, "show": 7, "virtual": 7, "multipl": [7, 11], "freez": 7, "full": 7, "sub": 7, "download": 7, "them": [7, 8, 9], "ran": 7, "lowest": 7, "more": [7, 11, 17, 19], "like": [7, 8], "matrix": 7, "ubuntu": 7, "3": [7, 13, 14, 21], "8": [7, 14, 21], "lockfil": 7, "root": [7, 10], "renam": 7, "commit": [7, 12, 13, 14], "pass": [7, 10], "exactli": 7, "onc": 7, "been": [7, 21], "good": [7, 17], "back": [7, 16], "unlock": 7, "earli": 7, "indic": [7, 11], "incom": 7, "restor": 7, "done": [8, 9], "find": 8, "function": [8, 13, 17], "error": 8, "coverag": 8, "commandlin": [8, 16, 21], "cov": 8, "xml": 8, "type": [9, 13, 14, 21], "definit": 9, "without": 9, "potenti": 9, "where": [9, 11, 16], "match": 9, "runtim": 10, "via": 10, "p": [10, 14], "verifi": 10, "docker": [10, 18], "fail": 10, "would": 10, "requir": [10, 12, 14, 17, 21], "podman": 10, "workstat": 10, "interchang": 10, "depend": [10, 18, 21], "call": [10, 17], "help": [10, 17], "other": 10, "line": [10, 13], "paramet": 10, "merg": 11, "keep": 11, "sync": 11, "between": 11, "rebas": 11, "fals": 11, "com": [11, 14, 21], "conflict": 11, "area": 11, "detail": 11, "split": [12, 16, 19], "four": [12, 17, 19], "categori": [12, 19], "access": [12, 19], "side": [12, 19], "bar": [12, 19], "contribut": [12, 16], "doc": [12, 13, 14], "sphinx": [12, 13, 14], "pytest": [12, 14], "analysi": [12, 13, 14], "mypi": [12, 13, 14], "pre": [12, 13, 14, 18], "pin": 12, "practic": [12, 19], "step": [12, 14, 19], "dai": 12, "dev": [12, 14], "task": 12, "architectur": 12, "decis": 12, "record": 12, "why": [12, 16, 19], "technic": [12, 17, 19], "materi": [12, 19], "conform": 13, "style": 13, "import": [13, 16], "order": [13, 17], "how": [13, 17], "guid": [13, 16, 17], "napoleon": 13, "extens": 13, "googl": 13, "consid": 13, "hint": 13, "signatur": 13, "def": 13, "func": 13, "arg1": 13, "str": [13, 20], "arg2": 13, "int": 13, "bool": 13, "summari": 13, "extend": 13, "descript": 13, "arg": 13, "return": 13, "valu": 13, "true": 13, "extract": 13, "underlin": 13, "convent": 13, "headl": 13, "head": 13, "These": 14, "instruct": 14, "minim": 14, "first": 14, "pandablock": [14, 18, 21], "ioc": [14, 18, 21], "either": 14, "host": 14, "machin": 14, "later": [14, 21], "vscode": 14, "virtualenv": 14, "m": [14, 16, 21], "bin": [14, 21], "activ": [14, 21], "devcontain": 14, "reopen": 14, "prompt": 14, "termin": [14, 21], "graph": 14, "tree": 14, "pipdeptre": 14, "parallel": 14, "templat": 16, "io": [16, 18], "write": [16, 17], "short": 16, "paragraph": 16, "peopl": 16, "pypi": 16, "put": 16, "imag": 16, "snippet": 16, "illustr": 16, "relev": 16, "introductori": 16, "pandablocks_ioc": 16, "__version__": [16, 20], "print": 16, "f": 16, "hello": 16, "section": 16, "grand": 17, "unifi": 17, "theori": 17, "david": 17, "la": 17, "secret": 17, "understood": 17, "softwar": [17, 21], "isn": 17, "thing": 17, "thei": 17, "tutori": 17, "refer": [17, 20], "explan": 17, "repres": 17, "purpos": 17, "creation": 17, "understand": 17, "implic": 17, "often": 17, "immens": 17, "topic": 17, "its": [18, 21], "alreadi": 18, "registri": 18, "ghcr": 18, "typic": 19, "usag": 19, "start": 19, "experienc": 19, "about": 19, "intern": 20, "calcul": 20, "pypa": 20, "setuptools_scm": 20, "recommend": 21, "interfer": 21, "path": 21, "featur": 21, "interfac": 21}, "objects": {"": [[20, 0, 0, "-", "pandablocks_ioc"]], "pandablocks_ioc.pandablocks_ioc": [[20, 1, 1, "", "__version__"]]}, "objtypes": {"0": "py:module", "1": "py:data"}, "objnames": {"0": ["py", "module", "Python module"], "1": ["py", "data", "Python data"]}, "titleterms": {"architectur": [0, 1], "decis": [0, 1, 2], "record": [0, 1], "1": 1, "statu": [1, 2], "context": [1, 2], "consequ": [1, 2], "2": 2, "adopt": 2, "python3": 2, "pip": 2, "skeleton": 2, "project": [2, 4], "structur": [2, 16], "build": [3, 10, 14], "doc": 3, "us": [3, 5, 8, 9], "sphinx": 3, "autobuild": 3, "contribut": 4, "issu": [4, 5], "discuss": 4, "code": [4, 13], "coverag": 4, "develop": [4, 12, 14], "guid": [4, 12, 19], "run": [5, 8, 9, 18], "lint": 5, "pre": 5, "commit": 5, "fix": 5, "vscode": 5, "support": 5, "make": 6, "releas": 6, "pin": 7, "requir": 7, "introduct": 7, "find": 7, "lock": 7, "file": 7, "appli": 7, "remov": 7, "depend": [7, 14], "from": 7, "ci": 7, "test": [8, 10, 14], "pytest": 8, "static": 9, "analysi": 9, "mypi": 9, "contain": [10, 18], "local": 10, "updat": 11, "tool": 11, "tutori": [12, 19], "how": [12, 16, 19], "explan": [12, 19], "refer": [12, 19], "standard": 13, "document": [13, 16, 17], "instal": [14, 21], "clone": 14, "repositori": 14, "see": 14, "what": 14, "wa": 14, "api": [15, 20], "index": 15, "pandablock": 16, "ioc": 16, "i": 16, "about": 17, "start": 18, "user": 19, "pandablocks_ioc": 20, "check": 21, "your": 21, "version": 21, "python": 21, "creat": 21, "virtual": 21, "environ": 21, "librari": 21}, "envversion": {"sphinx.domains.c": 3, "sphinx.domains.changeset": 1, "sphinx.domains.citation": 1, "sphinx.domains.cpp": 9, "sphinx.domains.index": 1, "sphinx.domains.javascript": 3, "sphinx.domains.math": 2, "sphinx.domains.python": 4, "sphinx.domains.rst": 2, "sphinx.domains.std": 2, "sphinx.ext.intersphinx": 1, "sphinx.ext.viewcode": 1, "sphinx": 60}, "alltitles": {"Architectural Decision Records": [[0, "architectural-decision-records"]], "1. Record architecture decisions": [[1, "record-architecture-decisions"]], "Status": [[1, "status"], [2, "status"]], "Context": [[1, "context"], [2, "context"]], "Decision": [[1, "decision"], [2, "decision"]], "Consequences": [[1, "consequences"], [2, "consequences"]], "2. Adopt python3-pip-skeleton for project structure": [[2, "adopt-python3-pip-skeleton-for-project-structure"]], "Build the docs using sphinx": [[3, "build-the-docs-using-sphinx"]], "Autobuild": [[3, "autobuild"]], "Contributing to the project": [[4, "contributing-to-the-project"]], "Issue or Discussion?": [[4, "issue-or-discussion"]], "Code coverage": [[4, "code-coverage"]], "Developer guide": [[4, "developer-guide"]], "Run linting using pre-commit": [[5, "run-linting-using-pre-commit"]], "Running pre-commit": [[5, "running-pre-commit"]], "Fixing issues": [[5, "fixing-issues"]], "VSCode support": [[5, "vscode-support"]], "Make a release": [[6, "make-a-release"]], "Pinning Requirements": [[7, "pinning-requirements"]], "Introduction": [[7, "introduction"]], "Finding the lock files": [[7, "finding-the-lock-files"]], "Applying the lock file": [[7, "applying-the-lock-file"]], "Removing dependency locking from CI": [[7, "removing-dependency-locking-from-ci"]], "Run the tests using pytest": [[8, "run-the-tests-using-pytest"]], "Run static analysis using mypy": [[9, "run-static-analysis-using-mypy"]], "Container Local Build and Test": [[10, "container-local-build-and-test"]], "Update the tools": [[11, "update-the-tools"]], "Developer Guide": [[12, "developer-guide"]], "Tutorials": [[12, null], [19, null]], "How-to Guides": [[12, null], [19, null]], "Explanations": [[12, null], [19, null]], "Reference": [[12, null], [19, null]], "Standards": [[13, "standards"]], "Code Standards": [[13, "code-standards"]], "Documentation Standards": [[13, "documentation-standards"]], "Developer install": [[14, "developer-install"]], "Clone the repository": [[14, "clone-the-repository"]], "Install dependencies": [[14, "install-dependencies"]], "See what was installed": [[14, "see-what-was-installed"]], "Build and test": [[14, "build-and-test"]], "API Index": [[15, "api-index"]], "PandABlocks-ioc": [[16, "pandablocks-ioc"]], "How the documentation is structured": [[16, "how-the-documentation-is-structured"]], "About the documentation": [[17, "about-the-documentation"]], "Run in a container": [[18, "run-in-a-container"]], "Starting the container": [[18, "starting-the-container"]], "User Guide": [[19, "user-guide"]], "API": [[20, "module-pandablocks_ioc"]], "pandablocks_ioc": [[20, "pandablocks-ioc"]], "Installation": [[21, "installation"]], "Check your version of python": [[21, "check-your-version-of-python"]], "Create a virtual environment": [[21, "create-a-virtual-environment"]], "Installing the library": [[21, "installing-the-library"]]}, "indexentries": {"module": [[20, "module-pandablocks_ioc"]], "pandablocks_ioc": [[20, "module-pandablocks_ioc"]], "pandablocks_ioc.__version__ (in module pandablocks_ioc)": [[20, "pandablocks_ioc.pandablocks_ioc.__version__"]]}})