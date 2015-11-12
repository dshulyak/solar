FROM ubuntu:14.04

WORKDIR /

ADD bootstrap/playbooks/celery.yaml /celery.yaml
ADD solar /solar
ADD solard /solard
ADD resources /resources
ADD templates /templates
ADD run.sh /run.sh
ADD f2s /f2s

RUN apt-get update
# Install pip's dependency: setuptools:
RUN apt-get install -y python python-dev python-distribute python-pip \
    libyaml-dev vim libffi-dev libssl-dev
RUN pip install ansible

RUN pip install riak peewee
RUN pip install -U setuptools>=17.1
RUN cd /solar && python setup.py install
RUN cd /solard && python setup.py install
RUN ansible-playbook -v -i "localhost," -c local /celery.yaml --skip-tags slave,stop
RUN pip install -U python-fuelclient
RUN apt-get install -y puppet
RUN gem install hiera
RUN mkdir -p /etc/puppet/hieradata/

CMD ["/run.sh"]
