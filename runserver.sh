#!/bin/bash
export PYTHONPATH=$(pwd)
export DJANGO_SETTINGS_MODULE=backend.settings
python3 surgicalm/manage.py runserver 0.0.0.0:8000

# Runserver Command
# chmod +x runserver.sh
# ./runserver.sh 
