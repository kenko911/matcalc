"""Calculator for elastic properties."""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np
import warnings

from pymatgen.analysis.elasticity import DeformedStructureSet, ElasticTensor, Strain
from pymatgen.analysis.elasticity.elastic import get_strain_state_dict
from pymatgen.io.ase import AseAtomsAdaptor

from .base import PropCalc
from .relaxation import RelaxCalc

if TYPE_CHECKING:
    from ase.calculators.calculator import Calculator
    from pymatgen.core import Structure


class ElasticityCalc(PropCalc):
    """
    Calculator for elastic properties.
    """

    def __init__(
        self,
        calculator: Calculator,
        norm_strains=(0.001, 0.003, 0.005, 0.01),
        shear_strains=(0.001, 0.003, 0.005, 0.01),
        fmax: float = 0.1,
        relax_structure: bool = True,
        use_equilibrium: bool = False,
    ) -> None:
        """
        Args:
            calculator: ASE Calculator to use.
            norm_strains: strain values to apply to each normal mode.
            shear_strains: strain values to apply to each shear mode.
            fmax: maximum force in the relaxed structure (if relax_structure).
            relax_structure: whether to relax the provided structure with the given calculator.
            use_equilibrium: whether to use the equilibrium stress and strain.
        """
        self.calculator = calculator
        self.norm_strains = norm_strains
        self.shear_strains = shear_strains
        self.relax_structure = relax_structure
        self.fmax = fmax
        self.use_equilibrium = use_equilibrium

    def calc(self, structure: Structure) -> dict:
        """
        Calculates elastic properties of Pymatgen structure with units determined by the calculator,
        (often the stress_weight).

        Args:
            structure: Pymatgen structure.

        Returns: {
            elastic_tensor: Elastic tensor as a pymatgen ElasticTensor object (in eV/A^3),
            shear_modulus_vrh: Voigt-Reuss-Hill shear modulus based on elastic tensor (in eV/A^3),
            bulk_modulus_vrh: Voigt-Reuss-Hill bulk modulus based on elastic tensor (in eV/A^3),
            youngs_modulus: Young's modulus based on elastic tensor (in eV/A^3),
            residuals_sum: Sum of squares of all residuals in the linear fits of the
            calculation of the elastic tensor,
            structure: The equilibrium structure used for the computation.
        }
        """
        if self.relax_structure:
            rcalc = RelaxCalc(self.calculator, fmax=self.fmax)
            structure = rcalc.calc(structure)["final_structure"]

        adaptor = AseAtomsAdaptor()
        deformed_structure_set = DeformedStructureSet(
            structure,
            self.norm_strains,
            self.shear_strains,
        )
        stresses = []
        for deformed_structure in deformed_structure_set:
            atoms = adaptor.get_atoms(deformed_structure)
            atoms.calc = self.calculator
            stresses.append(atoms.get_stress(voigt=False))

        strains = [
            Strain.from_deformation(deformation)
            for deformation in deformed_structure_set.deformations
        ]
        atoms = adaptor.get_atoms(structure)
        atoms.calc = self.calculator
        if self.use_equilibrium:
            elastic_tensor, residuals_sum = self._elastic_tensor_from_strains(
                strains, stresses, eq_stress=atoms.get_stress(voigt=False),
            )
        else:
            elastic_tensor, residuals_sum = self._elastic_tensor_from_strains(
                strains, stresses, eq_stress=None,
            )
        return {
            "elastic_tensor": elastic_tensor,
            "shear_modulus_vrh": elastic_tensor.g_vrh,
            "bulk_modulus_vrh": elastic_tensor.k_vrh,
            "youngs_modulus": elastic_tensor.y_mod,
            "residuals_sum": residuals_sum,
            "structure": structure,
        }

    def _elastic_tensor_from_strains(
        self,
        strains,
        stresses,
        eq_stress=None,
        tol: float = 1e-7,
    ):
        """
        Slightly modified version of Pymatgen function
        pymatgen.analysis.elasticity.elastic.ElasticTensor.from_independent_strains;
        this is to give option to discard eq_stress,
        which (if the structure is relaxed) tends to sometimes be
        much lower than neighboring points.
        Also has option to return the sum of the squares of the residuals
        for all of the linear fits done to compute the entries of the tensor.
        """
        strain_states = [tuple(ss) for ss in np.eye(6)]
        ss_dict = get_strain_state_dict(
            strains, stresses, eq_stress=eq_stress, add_eq=self.use_equilibrium
        )
        if not set(strain_states) <= set(ss_dict):
            raise ValueError(
                f"Missing independent strain states: {set(strain_states) - set(ss_dict)}"
            )
        if len(set(ss_dict) - set(strain_states)) > 0:
            warnings.warn(
                "Extra strain states in strain-stress pairs are neglected in independent strain fitting"
            )
        c_ij = np.zeros((6, 6))
        residuals_sum = 0
        for i in range(6):
            istrains = ss_dict[strain_states[i]]["strains"]
            istresses = ss_dict[strain_states[i]]["stresses"]
            for j in range(6):
                fit = np.polyfit(istrains[:, i], istresses[:, j], 1, full=True)
                c_ij[i, j] = fit[0][0]
                residuals_sum += fit[1][0]
        c = ElasticTensor.from_voigt(c_ij)
        return c.zeroed(tol), residuals_sum
