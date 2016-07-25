#!/usr/bin/env python

from setuptools import setup

setup(name='UWS',
      version='1.5',
      description='Universal Web SCADA',
      author='José Antonio Casares González',
      author_email='josecasares@gmail.com',
      url='http://josecasares.com/',
      packages=[],
      install_requires=['sqlalchemy','pymodbus3','freeopcua','autobahn']
     )
