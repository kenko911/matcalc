[![GitHub license](https://img.shields.io/github/license/materialsvirtuallab/matcalc)](https://github.com/materialsvirtuallab/matcalc/blob/main/LICENSE)
[![Linting](https://github.com/materialsvirtuallab/matcalc/workflows/Linting/badge.svg)](https://github.com/materialsvirtuallab/matcalc/workflows/Linting/badge.svg)
[![Testing](https://github.com/materialsvirtuallab/matcalc/workflows/Testing/badge.svg)](https://github.com/materialsvirtuallab/matcalc/workflows/Testing/badge.svg)
[![codecov](https://codecov.io/gh/materialsvirtuallab/matcalc/branch/main/graph/badge.svg?token=OR7Z9WWRRC)](https://codecov.io/gh/materialsvirtuallab/matcalc)
[![Requires Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg?logo=python&logoColor=white)](https://python.org/downloads)

# Introduction

MatCalc is a python library for calculating materials properties from the potential energy surface (PES). The
PES can be from DFT or, more commonly, from machine learning interatomic potentials (MLIPs).

Calculating various materials properties can require relatively involved setup of various simulation codes. The
goal of MatCalc is to provide a simplified, consistent interface to access these properties with any
parameterization of the PES.

# Outline

The main base class in MatCalc is PropCalc (property calculator). All PropCalc subclasses should implement a
`calc(structure) -> dict` method that takes in a Pymatgen Structure and returns a dict of properties.

In general, PropCalc should be initialized with an ML model or ASE calculator, which is then used by either ASE,
LAMMPS or some other simulation code to perform calculations of properties.
