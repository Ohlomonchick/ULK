#!/bin/bash
export PROD=True
export USE_POSTGRES=yes

#source /mnt/c/Users/Dmitry/PycharmProjects/Cyberpolygon/polygon_linux/bin/activate


# Initialize pyenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# Set pyenv global version
pyenv global 3.11.13



python3 manage.py runapscheduler