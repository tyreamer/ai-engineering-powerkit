.PHONY: validate test doctor package

validate:
	python3 tools/validate.py

test:
	python3 -m unittest discover -s tests -v

doctor:
	python3 tools/doctor.py --target .

package: validate
	python3 tools/package.py
