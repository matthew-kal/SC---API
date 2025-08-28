#!/bin/bash
export PYTHONPATH=$(pwd)
export DJANGO_SETTINGS_MODULE=backend.settings
python3 surgicalm/manage.py dbshell

# Runserver Command
# chmod +x rundb.sh
# ./rundb.sh