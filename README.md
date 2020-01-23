# xmls2pb 
Scripts to transform realtime xml data into google protobuf format

### Requirements
Python 3.6 or greater

### Installing
Install dependencies:  
```
pip3 install -r requirements.txt
``` 

Copy configuration in `config-orig.py` to config.py and add customization.

### Running
Start the script with
```
python ./run.py
```
or for more logging information:
```
python ./run.py --log DEBUG 
```

### Running as a service on EC2
The included file `xml2pb.service` is a basic systemd service. Place it somewhere 
that systemd looks, such as `/etc/systemd/system` then reload, enable, and start:
```
sudo systemctl daemon-reload
sudo systemctl enable xml2pd.service
sudo systemctl start xml2pd.service
```
Check for status with:

```
sudo systemctl status xml2pd.service
```


### Authors
* **Mark Meyer** - *Initial work* - [Github](https://github.com/mark-meyer)
