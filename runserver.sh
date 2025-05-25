#!/bin/bash
export PYTHONPATH=$(pwd)
export DJANGO_SETTINGS_MODULE=backend.settings
python surgicalm/manage.py runserver

# Runserver Command
# chmod +x runserver.sh
# ./runserver.sh