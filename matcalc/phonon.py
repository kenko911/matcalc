"""Calculator for phonon properties."""

from __future__ import annotations

from typing import TYPE_CHECKING

import phonopy
from phonopy.file_IO import write_FORCE_CONSTANTS
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.io.phonopy import get_phonopy_structure, get_pmg_structure

from .base import PropCalc
from .relaxation import RelaxCalc

if TYPE_CHECKING:
    from ase.calculators.calculator import Calculator
    from numpy.typing import ArrayLike
    from phonopy.structure.atoms import PhonopyAtoms
    from pymatgen.core import Structure


class PhononCalc(PropCalc):
    """Calculator for phonon properties."""

    def __init__(
        self,
        calculator: Calculator,
        atom_disp: float = 0.015,
        supercell_matrix: ArrayLike = ((2, 0, 0), (0, 2, 0), (0, 0, 2)),
        t_step: float = 10,
        t_max: float = 1000,
        t_min: float = 0,
        fmax: float = 0.1,
        optimizer: str = "FIRE",
        relax_structure: bool = True,
        write_force_constants: bool = False,
        write_band_structure: bool = False,
        write_total_dos: bool = False,
        write_phonon: bool = True,
    ) -> None:
        """
        Args:
            calculator: ASE Calculator to use.
            fmax: Max forces. This criterion is more stringent than for simple relaxation.
                Defaults to 0.1 (in eV/Angstrom)
            optimizer: Optimizer used for RelaxCalc.
            atom_disp: Atomic displacement (in Angstrom).
            supercell_matrix: Supercell matrix to use. Defaults to 2x2x2 supercell.
            t_step: Temperature step (in Kelvin).
            t_max: Max temperature (in Kelvin).
            t_min: Min temperature (in Kelvin).
            relax_structure: Whether to first relax the structure. Set to False if structures
                provided are pre-relaxed with the same calculator.
            write_force_constants: Whether to save force constants. Set to False for storage
                conservation. This file can be very large, be careful when doing high-throughput
                calculations.
            write_band_structure: Whether to calculate and save band structure (in yaml format).
                Defaults to False.
            write_total_dos: Whether to calculate and save density of states (in dat format).
                Defaults to False.
            write_phonon: Whether to save phonon object. Set to True to save necesssary phonon
                calculation results. Band structure, density of states, thermal properties,
                etc. can be rebuilt from this file using the phonopy API via phonopy.load("phonon.yaml")
        """
        self.calculator = calculator
        self.atom_disp = atom_disp
        self.supercell_matrix = supercell_matrix
        self.fmax = fmax
        self.optimizer = optimizer
        self.relax_structure = relax_structure
        self.t_step = t_step
        self.t_max = t_max
        self.t_min = t_min
        self.write_force_constants = write_force_constants
        self.write_band_structure = write_band_structure
        self.write_total_dos = write_total_dos
        self.write_phonon = write_phonon

    def calc(self, structure: Structure) -> dict:
        """
        Calculates thermal properties of Pymatgen structure with phonopy.

        Args:
            structure: Pymatgen structure.

        Returns:
        {
            phonon: Phonopy object with force constants produced
            thermal_properties:
                {
                    temperatures: list of temperatures in Kelvin,
                    free_energy: list of Helmholtz free energies at corresponding temperatures in kJ/mol,
                    entropy: list of entropies at corresponding temperatures in J/K/mol,
                    heat_capacity: list of heat capacities at constant volume at corresponding temperatures in J/K/mol,
                    The units are originally documented in phonopy.
                    See phonopy.Phonopy.run_thermal_properties()
                    (https://github.com/phonopy/phonopy/blob/develop/phonopy/api_phonopy.py#L2591)
                    -> phonopy.phonon.thermal_properties.ThermalProperties.run()
                    (https://github.com/phonopy/phonopy/blob/develop/phonopy/phonon/thermal_properties.py#L498)
                    -> phonopy.phonon.thermal_properties.ThermalPropertiesBase.run_free_energy()
                    (https://github.com/phonopy/phonopy/blob/develop/phonopy/phonon/thermal_properties.py#L217)
                    phonopy.phonon.thermal_properties.ThermalPropertiesBase.run_entropy()
                    (https://github.com/phonopy/phonopy/blob/develop/phonopy/phonon/thermal_properties.py#L233)
                    phonopy.phonon.thermal_properties.ThermalPropertiesBase.run_heat_capacity()
                    (https://github.com/phonopy/phonopy/blob/develop/phonopy/phonon/thermal_properties.py#L225)
                }
        }
        """
        if self.relax_structure:
            relaxer = RelaxCalc(self.calculator, fmax=self.fmax, optimizer=self.optimizer)
            structure = relaxer.calc(structure)["final_structure"]
        cell = get_phonopy_structure(structure)
        phonon = phonopy.Phonopy(cell, self.supercell_matrix)
        phonon.generate_displacements(distance=self.atom_disp)
        disp_supercells = phonon.supercells_with_displacements
        phonon.forces = [
            _calc_forces(self.calculator, supercell) for supercell in disp_supercells if supercell is not None
        ]
        phonon.produce_force_constants()
        phonon.run_mesh()
        phonon.run_thermal_properties(t_step=self.t_step, t_max=self.t_max, t_min=self.t_min)
        if self.write_force_constants:
            write_FORCE_CONSTANTS(phonon.force_constants, filename="FORCE_CONSTANTS")
        if self.write_band_structure:
            phonon.auto_band_structure(write_yaml=True, filename="phonon_band_structure.yaml")
        if self.write_total_dos:
            phonon.auto_total_dos(write_dat=True, filename="phonon_total_dos.dat")
        if self.write_phonon:
            phonon.save("phonon.yaml")
        return {"phonon": phonon, "thermal_properties": phonon.get_thermal_properties_dict()}


def _calc_forces(calculator: Calculator, supercell: PhonopyAtoms) -> ArrayLike:
    """
    Helper to compute forces on a structure.

    Args:
        calculator: ASE Calculator
        supercell: Supercell from phonopy.

    Return:
        forces
    """
    struct = get_pmg_structure(supercell)
    atoms = AseAtomsAdaptor.get_atoms(struct)
    atoms.calc = calculator
    return atoms.get_forces()
