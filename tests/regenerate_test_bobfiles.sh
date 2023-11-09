#!/bin/bash

echo "REGENERATING TEST BOBFILES (this needs to be done through pytest)"
pytest -q --no-cov --no-summary --no-header tests/test-bobfiles/regenerate_test_bobfiles.py
