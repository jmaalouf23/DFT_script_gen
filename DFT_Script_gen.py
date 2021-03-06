import os
from os import path
import sys
import getopt
import rdkit
from rdkit import Chem
import subprocess
import pandas as pd
import argparse
from DFT_utils import b2bf, bf2b


def GetSpinMultiplicity(Mol, CheckMolProp = True):
    """Get spin multiplicity of a molecule. The spin multiplicity is either
    retrieved from 'SpinMultiplicity' molecule property or calculated from
    from the number of free radical electrons using Hund's rule of maximum
    multiplicity defined as 2S + 1 where S is the total electron spin. The
    total spin is 1/2 the number of free radical electrons in a molecule.

    Arguments:
    Mol (object): RDKit molecule object.
    CheckMolProp (bool): Check 'SpinMultiplicity' molecule property to
    retrieve spin multiplicity.

    Returns:
    int : Spin multiplicity.

    """

    Name = 'SpinMultiplicity'
    if (CheckMolProp and Mol.HasProp(Name)):
        return int(float(Mol.GetProp(Name)))

    # Calculate spin multiplicity using Hund's rule of maximum multiplicity...
    NumRadicalElectrons = 0
    for Atom in Mol.GetAtoms():
        NumRadicalElectrons += Atom.GetNumRadicalElectrons()

    TotalElectronicSpin = NumRadicalElectrons/2
    SpinMultiplicity = 2 * TotalElectronicSpin + 1

    return int(SpinMultiplicity)


def mkgauss_input_from_xyz(rn,smiles,solvorgas='gas',solvmethod=None,solvent=None,functional='B3LYP',basis='6-31++G**',mem='180GB',mult=True,charge=True,pop_analysis=False,single_point=False,chk=False,n_proc_shared=48):
    
    """ Make a gaussian input script from an xyz file similar to the format produced by
    open babel. Ideally takes the output of mk_xyz_from_smiles_string or mk_xyz_from_smi.

    Arguments:
    rn (object): path to output file including the filename. Do not include the extension, such as .com


    Returns:
    gaussian input file containing functional, basis set, xyz coordinates, etc.

    """
    
    writepath = os.path.join(os.getcwd(),f'{rn}.xyz')
    short_filename=os.path.basename(os.path.normpath(rn))
    
    mode = 'r' if os.path.exists(writepath) else 'w'
    with open(writepath, mode) as f:
        xyz=f.readlines()

    writepath = os.path.join(os.getcwd(),f'{rn}.com')
    
    mode = 'a' if os.path.exists(writepath) else 'w'
    mol=Chem.MolFromSmiles(smiles)
    
    if charge and isinstance(charge,bool):
        pc=Chem.rdmolops.GetFormalCharge(mol)
    else:
        pc=charge
    #get multiplcity
    
    if mult and isinstance(mult,bool):
        mult=GetSpinMultiplicity(mol)
        

    with open(writepath, mode) as f:
        f.truncate(0)
        f.write(f"%Mem={mem}\n")
        if chk:
            f.write(f"%chk={short_filename}.chk\n")
            
        f.write(f"%NProcShared={n_proc_shared}\n")
        #f.write(f"#p {functional}/{bf2b(basis)} Opt=(calcall,noeigentest,maxcycles=120) Freq\n")
        
        
        if single_point:
            sp=''
        else:
            sp='Opt=(maxcycles=120)' 
        if pop_analysis:
            p='Pop=Full iop(3/33=1)'
        else:
            p=''
            
        f.write(f"#p {functional}/{bf2b(basis)} {p} {sp} Freq\n")
        
        if solvorgas=='solv':
            f.write(f"SCRF=({solvmethod},solvent={solvent})\n\n")
            f.write('solventopt\n\n')
        else:
            f.write('\n\n')
        f.write(f'{pc} {mult}\n')
        for i,line in enumerate(xyz):
            if i>1:
                f.write(line)
        f.write('\n')
        if solvorgas=='solv':
            f.write('RADII=BONDI\n')
        f.write('\n')
        f.close()

def mkgauss_submission_script(path,partition='xeon-p8',job_name='name', time='5-0:00:00',num_cpus=48,mem_per_cpu=4000):
    
    short_filename=os.path.basename(os.path.normpath(path))
    writepath = os.path.join(os.getcwd(),f'{path}.sh')
    short_filename=os.path.basename(os.path.normpath(path))
    mode = 'a' if os.path.exists(writepath) else 'w'

    with open(writepath, mode) as f:
        f.truncate(0)
        f.write("#!/bin/bash -l\n")
        f.write(f"#SBATCH --partition={partition}\n")
        f.write(f"#SBATCH -J {short_filename}\n")
        f.write(f"#SBATCH -N 1\n")
        f.write(f"#SBATCH -c {num_cpus}\n")
        f.write(f"#SBATCH --time={time}\n")
        f.write(f"#SBATCH --mem-per-cpu={mem_per_cpu}\n")
        f.write(f"#SBATCH --exclusive\n\n")
        
        f.write(f"export g16root=/home/gridsan/groups/manthiram_lab/gaussian\n\n")
        f.write(f"export PATH=$g16root/g16/:$g16root/gv:$PATH\n\n")
        
        f.write(f"echo \"Gaussian PATH\"\n")
        f.write(f"which g16\n")
        f.write(f"input={short_filename}.com\n")
        
        f.write(f'echo "============================================================"\n')
        f.write(f'echo "Job ID : $SLURM_JOB_ID"\n')
        f.write(f'echo "Job Name : $SLURM_JOB_NAME"\n')
        f.write(f'echo "Starting on : $(date)"\n')
        f.write(f'echo "Running on node : $SLURMD_NODENAME"\n')
        f.write(f'echo "Current directory : $(pwd)"\n')

        f.write(f'echo "============================================================"\n\n')
        
        f.write(f'export GAUSS_SCRDIR=/home/gridsan/groups/manthiram_lab/scratch/$SLURM_JOB_NAME-$SLURM_JOB_ID\n\n')
        
        f.write(f'export GAUSS_SCRDIR\n')
        f.write(f'. $g16root/g16/bsd/g16.profile\n\n')
                
                
        f.write(f'echo "GAUSS_SCRDIR : $GAUSS_SCRDIR"\n')
        f.write(f'mkdir -p $GAUSS_SCRDIR\n')
        f.write(f'chmod 750 $GAUSS_SCRDIR\n')
        f.write(f'g16 $input\n\n')
        
        f.write(f'rm -rf $GAUSS_SCRDIR')
        
        f.write('\n')
        f.close()


