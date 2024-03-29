# The Reproducible Experimentation System (RES)
## Table of Contents
- [The Reproducible Experimentation System (RES)](#the-reproducible-experimentation-system-res)
    - [Description](#description)
    - [Limitations](#limitations)
    - [Installation](#installation)
        - [Requirements](#requirements)
        - [Windows](#windows)
        - [Linux](#linux)
    - [Run The GUI](#run-the-gui)
    - [Run Engine Tests](#run-engine-tests)
    - [Troubleshooting](#troubleshooting)

### Description
RES is a wrapper system that enables analysts and researchers to easily create, package, and execute experiments that are generated using virtual machines.

The current version of RES supports VirtualBox machines. 

### Limitations
* The system currently does not allow entry of custom VM commands. This feature is forthcoming.

### Installation
RES has been tested on:
* Windows 10 (64-bit)
* Ubuntu 16.04 LTE (64-bit)

##### Requirements
* [Python 3.6 (64-bit) ](https://www.python.org/downloads/release/python-360/)
* [VirtualBox 6.1.6](https://www.virtualbox.org/wiki/Downloads)
* [Several Other Python packages] (see requirements.txt)
##### Windows
Clone the source and then cd into the directory:
```
git clone https://github.com/raistlinJ/res
cd res
```
Setup and activate the virtualenv container
```
python -m venv venv
venv\Scripts\activate
```
Install the res python dependencies
```
pip install -r requirements.txt
```

##### Linux
Install Python >= 3.5 (if you already have it, skip this step):
```
sudo apt-get install libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev

wget https://www.python.org/ftp/python/3.6.9/Python-3.6.9.tgz
tar zxvf Python-3.6.9.tgz
cd Python-3.6.9
./configure
make
sudo make install
```
Setup and activate the virtualenv container
```
python3 -m venv venv
```
Clone RES repo 
```  
git clone https://github.com/raistlinJ/res
cd res
```
Activate the venv and install python dependencides
```
source venv/bin/activate
pip3 install -r requirements.txt
```

To run the GUI, follow the steps in [Run the GUI](#run-the-gui).
To run the engine tests, follow the steps in [Run Engine Tests](#run-engine-tests).


### Run the GUI
Navigate to the folder where you downloaded res and activate the virtualenv container
```
cd res
```
##### Linux
```
source venv\bin\activate
```
##### Windows
```
venv\Scripts\activate
```
##### Both
Start the GUI
```
python main.py
```
A sample RES file can be downloaded [here](https://bit.ly/2wP3Gzc). After downloading the file, right-click and select to Import the file.

### Run Engine Tests
A driver program is included that will demonstrate several of the functions provided by RES.

Download the Sample RES file from [here](https://bit.ly/2wP3Gzc) and save it into the following directory
```
res/src/main/python/ExperimentData/samples/
```
Activate the virtualenv container
```
cd res
(Windows)
venv\Scripts\activate
(Linux)
source venv\bin\activate
```
Run the Engine Tests:
```
cd src/main/python/
python TestEngine.py
```

### Troubleshooting

Please contribute!
