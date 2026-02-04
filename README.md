
# Setup Up

## Install Rust

Install rustup through your package manager or by following the intructions at https://rustup.rs

You may need to run
```sh
rustup default stable
```
to install the current `stable` release.


## Setup Python Enviroment

```sh
python -m venv .venv
. ./.venv/bin/activate
pip install -r requirements.txt
```


## Configure the tester
Modify the `workshop_config.py` file to provide the correct inputs and tell the tester
how to check that the results match.


## Run the comparison
```sh
python run_workshop.py
```
(the first run will take significantly longer as dependencies are compiled) 
