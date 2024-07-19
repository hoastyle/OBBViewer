# Installation
## Recv
```bash
$ pip install pyzmq pygame PyOpenGL
```

## Sender
```bash
$ sudo apt-get install libzmq3-dev nlohmann-json3-dev
$ g++ -std=c++11 sender.cpp -o sender -lzmq
$ cd thirdparty
```

### Install cppzmq
Download cppzmq https://github.com/zeromq/cppzmq.git

```bash
$ mkdir build;
$ cd build;
$ cmake ../;
$ make;
$ sudo make install
```
