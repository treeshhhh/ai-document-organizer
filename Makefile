PYTHON ?= python3
.PHONY: run test model evaluate
run:
	$(PYTHON) app.py
model:
	$(PYTHON) setup_model.py
test:
	$(PYTHON) -m unittest discover -s tests -v
evaluate:
	$(PYTHON) evaluate.py
