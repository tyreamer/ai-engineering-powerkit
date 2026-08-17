.PHONY: validate test doctor wheel package

validate:
	python3 tools/validate.py

test:
	python3 -m unittest discover -s tests -v

doctor:
	python3 tools/doctor.py --target .

wheel:
	python3 -m pip wheel . --no-deps --wheel-dir dist/wheels

package: validate
	python3 tools/package.py
