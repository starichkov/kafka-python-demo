#export COVERAGE_PROCESS_START=$(pwd)/.coveragerc
rm -r htmlcov/
rm .coverage
rm .coverage.*
pytest --cov --cov-report=term-missing
coverage html
#xdg-open htmlcov/index.html