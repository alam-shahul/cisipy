FROM us.gcr.io/broad-dsp-gcr-public/terra-jupyter-python:0.0.14

USER root
#this makes it so pip runs as root, not the user
ENV PIP_USER=false

# Installing Apache
WORKDIR /opt
RUN wget https://mirrors.koehn.com/apache/maven/maven-3/3.6.3/binaries/apache-maven-3.6.3-bin.tar.gz \
 && tar -xzvf /opt/apache-maven-*.tar.gz
ENV JAVA_HOME /usr/lib/jvm/default-java
ENV M2_HOME /opt/apache-maven-3.6.3
ENV MAVEN_HOME /opt/apache-maven-3.6.3
ENV PATH ${M2_HOME}/bin:${PATH}

# Installing ant
RUN wget http://mirror.cogentco.com/pub/apache//ant/binaries/apache-ant-1.10.8-bin.tar.gz \
 && tar -xzvf apache-ant-1.10.8-bin.tar.gz
ENV ANT_HOME /opt/apache-ant-1.10.8
ENV PATH ${ANT_HOME}/bin:${PATH}

# Define working directory.
WORKDIR /opt/fiji

# Install Fiji.
RUN wget https://downloads.imagej.net/fiji/latest/fiji-nojre.zip \
 && unzip fiji-nojre.zip \
 && rm fiji-nojre.zip

# Downloading better Imagej-linux64 launcher and moving to correct location
RUN wget https://maven.scijava.org/service/local/repositories/snapshots/content/net/imagej/imagej-launcher/5.0.4-SNAPSHOT/imagej-launcher-5.0.4-20200804.171457-19-linux64.exe
RUN chmod u+x imagej-launcher-5.0.4-20200804.171457-19-linux64.exe
RUN mv imagej-launcher-5.0.4-20200804.171457-19-linux64.exe Fiji.app/ImageJ-linux64

# Install BigStitcher
RUN /opt/fiji/Fiji.app/ImageJ-linux64 --update edit-update-site BigStitcher https://sites.imagej.net/BigStitcher/ \
 && /opt/fiji/Fiji.app/ImageJ-linux64 --update update

# Add fiji to the PATH
ENV PATH $PATH:/opt/fiji/Fiji.app
ENV PATH $PATH:/home/jupyter-user/miniconda/bin/

RUN conda config --add channels conda-forge \
 && conda config --set channel_priority strict \
 && conda create -n preprocessing python=3.8

SHELL ["conda", "run", "-n", "preprocessing", "/bin/bash", "-c"]

WORKDIR /opt
RUN pip install setuptools \
 && pip install Cython \
 && git clone https://github.com/kivy/pyjnius \
 && cd pyjnius \
 && make \
 && python setup.py install

ENV PYJNIUS_JAR /opt/pyjnius/build/pyjnius.jar

RUN pip -V \
 && pip install --upgrade pip \
 && pip install pyimagej==0.5.0 \
 && pip install numpy==1.18.1 \
 && pip install Cython \
 && pip install scipy==1.5. \
 # Spip for cisipy
 && pip install pyimagej==0.5.0 \
 && pip install starfish==0.2.1 \
 && pip install python-bioformats==1.5.2 \
 && pip install tifffile==2020.7.24 \
 && pip install nd2reader==3.2.3 \
 && pip install sympy==1.5.1 \
 && pip install toml \
 && pip install cisipy==0.0.14 

RUN apt-get update && apt-get install -yq --no-install-recommends \
    build-essential    \
    cython             \
    git                \
    libmysqlclient-dev \
    libhdf5-dev        \
    libxml2-dev        \
    libxslt1-dev       \
    python3.8-dev      \
    python-h5py        \
    python-matplotlib  \
    python-mysqldb     \
    python-pytest      \
    python-vigra       \
    python-wxgtk3.0    \
    python-zmq         \
    libgtk-3-dev       \
    gcc                \
    g++

ENV PATH $PATH:/usr/lib/gcc/x86_64-linux-gnu/7/

WORKDIR /opt

RUN apt-get install -yq --no-install-recommends \
    # Necessary for CellProfiler
    dpkg-dev                            \
    freeglut3-dev                       \
    libgl1-mesa-dev                     \
    libglu1-mesa-dev                    \
    libgstreamer-plugins-base1.0-dev    \
    libgtk-3-dev                        \
    libjpeg-dev                         \
    libnotify-dev                       \
    libpng-dev                          \
    libsdl2-dev                         \
    libsm-dev                           \
    libtiff-dev                         \
    libwebkit2gtk-4.0-dev               \
    libxtst-dev                         \
    # Include tmux to aid interactive mode because why not                         
    tmux

RUN pip install -U \
    -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-18.04/wxPython-4.1.0-cp38-cp38-linux_x86_64.whl \
    wxPython

RUN apt-get install -yq --no-install-recommends \
    libsdl2-mixer-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-2.0-0

RUN git clone https://github.com/CellProfiler/CellProfiler.git \
 && cd CellProfiler \
 && pip install . \
 && cd ..

# Not explicitly necessary, but allows us to run GUI (bug with CellProfiler installation)
RUN cp /opt/CellProfiler/cellprofiler/gui/html/* \
    /home/jupyter-user/miniconda/envs/preprocessing/lib/python3.8/site-packages/cellprofiler/gui/html/

# Installing spams

RUN apt-get install -yq --no-install-recommends \
    libopenblas-dev \
    libopenblas-base \
    liblapack-dev

RUN wget https://gforge.inria.fr/frs/download.php/file/36849/spams-python3-v2.6-2017-06-06.tar.gz \
 && tar -xzvf spams-python3-v2.6-2017-06-06.tar.gz \
 && ls \
 && cd spams-python3 \
 && pip install distro \
 && python setup.py build \
 && python setup.py install --prefix="/home/jupyter-user/miniconda/envs/preprocessing/"

RUN  conda install -y sphinx
 
ENV USER jupyter-user
USER $USER
#we want pip to install into the user's dir when the notebook is running
ENV PIP_USER=true
#RUN bash -c "ls /home/jupyter-user/miniconda/bin/pip"

WORKDIR $HOME

# Note: this entrypoint is provided for running Jupyter independently of Leonardo.
# When Leonardo deploys this image onto a cluster, the entrypoint is overwritten to enable
# additional setup inside the container before execution.  Jupyter execution occurs when the
# init-actions.sh script uses 'docker exec' to call run-jupyter.sh.
ENTRYPOINT ["/usr/local/bin/jupyter", "notebook"]
