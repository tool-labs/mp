#!/bin/sh
# Run a job of the Flask app with the webservice's venv, e.g.
#   sh ~/mp/jobs/run-python-job.sh update-rc
cd "$HOME/mp/webapp" || exit 1
exec "$HOME/www/python/venv/bin/python" -m mpweb.jobs "$@"
