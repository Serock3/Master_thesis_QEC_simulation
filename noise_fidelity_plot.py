# %% Import modules
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from qiskit import *
from qiskit.visualization import plot_histogram

# Import from Qiskit Aer noise module
from qiskit.providers.aer.noise import pauli_error,depolarizing_error
from qiskit.providers.aer.noise import (thermal_relaxation_error, 
                                        amplitude_damping_error, 
                                        phase_damping_error, 
                                        phase_amplitude_damping_error
                                        )

from qiskit.quantum_info import partial_trace
from qiskit.quantum_info import DensityMatrix
from qiskit.quantum_info import state_fidelity

# Our own files
from simulator_program.custom_noise_models import phase_amplitude_model
from simulator_program.custom_noise_models import thermal_relaxation_model
from simulator_program.custom_transpiler import *
from simulator_program.stabilizers import *

# %%
def logical_states():
    logical_0 = np.zeros(2**5)
    logical_0[0b00000] = 1/4
    logical_0[0b10010] = 1/4
    logical_0[0b01001] = 1/4
    logical_0[0b10100] = 1/4
    logical_0[0b01010] = 1/4
    logical_0[0b11011] = -1/4
    logical_0[0b00110] = -1/4
    logical_0[0b11000] = -1/4
    logical_0[0b11101] = -1/4
    logical_0[0b00011] = -1/4
    logical_0[0b11110] = -1/4
    logical_0[0b01111] = -1/4
    logical_0[0b10001] = -1/4
    logical_0[0b01100] = -1/4
    logical_0[0b10111] = -1/4
    logical_0[0b00101] = 1/4

    logical_1 = np.zeros(2**5)
    logical_1[0b11111] = 1/4
    logical_1[0b01101] = 1/4
    logical_1[0b10110] = 1/4
    logical_1[0b01011] = 1/4
    logical_1[0b10101] = 1/4
    logical_1[0b00100] = -1/4
    logical_1[0b11001] = -1/4
    logical_1[0b00111] = -1/4
    logical_1[0b00010] = -1/4
    logical_1[0b11100] = -1/4
    logical_1[0b00001] = -1/4
    logical_1[0b10000] = -1/4
    logical_1[0b01110] = -1/4
    logical_1[0b10011] = -1/4
    logical_1[0b01000] = -1/4
    logical_1[0b11010] = 1/4

    return [logical_0, logical_1]

# %% =================  Testing noise model + stabilizer ======================
# DEFINE AND TRANSPILE THE CIRCUIT

# Define our registers
qb = QuantumRegister(5, 'code_qubit')
an = AncillaRegister(2, 'ancilla_qubit')
cr = ClassicalRegister(5, 'syndrome_bit') # The typical register
readout = ClassicalRegister(5, 'readout')

registers = StabilizerRegisters(qb, an, cr, readout)
circ = get_empty_stabilizer_circuit(registers)

# Settings for circuit
n_cycles = 1
reset=True
flag=False
recovery=False

# Get the circuit
circ.x(qb[0])
circ += get_full_stabilizer_circuit(registers,
    n_cycles=n_cycles,
    reset=reset,
    recovery=recovery,
    flag=flag,
)

# Transpilation
routing_method = 'sabre'  # basic lookahead stochastic sabre
initial_layout = None  # Overwriting the above layout
layout_method = 'sabre'  # trivial 'dense', 'noise_adaptive' sabre
translation_method = None  # 'unroller',  translator , synthesis
optimization_levels = [0,1,2]
repeats = 10
circuit_list = [circ]
for optimization_level in optimization_levels:
    circ_t = shortest_transpile_from_distribution(
        circ,
        print_cost=False,
        repeats=repeats,
        routing_method=routing_method,
        initial_layout=initial_layout,
        layout_method=layout_method,
        translation_method=translation_method,
        optimization_level=0,
        **WAQCT_device_properties
    )
    circuit_list.append(circ_t)

#circ_t0 = shortest_transpile_from_distribution(
#    circ,
#    print_depths=False,
#    repeats=repeats,
#    routing_method=routing_method,
#    initial_layout=initial_layout,
#    layout_method=layout_method,
#    translation_method=translation_method,
#    optimization_level=1,
#    **WAQCT_device_properties
#)
#circ_t1 = shortest_transpile_from_distribution(
#    circ,
#    print_depths=False,
#    repeats=repeats,
#    routing_method=routing_method,
#    initial_layout=initial_layout,
#    layout_method=layout_method,
#    translation_method=translation_method,
#    optimization_level=1,
#    **WAQCT_device_properties
#)
#circ_t2 = shortest_transpile_from_distribution(
#    circ,
#    print_depths=False,
#    repeats=repeats,
#    routing_method=routing_method,
#    initial_layout=initial_layout,
#    layout_method=layout_method,
#    translation_method=translation_method,
#    optimization_level=2,
#    **WAQCT_device_properties
#)

# Error free run for fidelity measurements
correct_state = []
for circuit in circuit_list:
    results = execute(
        circuit,
        Aer.get_backend('qasm_simulator'),
        noise_model=None,
        shots=1,
    ).result()

    correct_state.append(
        results.data()['snapshots']['statevector']['stabilizer_0'][0]
    )

#results_t0 = execute(
#    circ_t0,
#    Aer.get_backend('qasm_simulator'),
#    noise_model=None,
#    shots=1,
#).result()
#logical_t0 = results_t0.data()['snapshots']['statevector']['stabilizer_0'][0]
#results_t1 = execute(
#    circ_t1,
#    Aer.get_backend('qasm_simulator'),
#    noise_model=None,
#    shots=1,
#).result()
#logical_t1 = results_t1.data()['snapshots']['statevector']['stabilizer_0'][0]
#results_t2 = execute(
#    circ_t2,
#    Aer.get_backend('qasm_simulator'),
#    noise_model=None,
#    shots=1,
#).result()
#logical_t2 = results_t2.data()['snapshots']['statevector']['stabilizer_0'][0]



# %% Functions for analyzing results
def select_no_errors(mem):
    '''Gives array of booleans corresponding to the shots without errors'''
    return np.array( [int(item[6:10]) for item in mem] ) == 0

def get_fidelity_data(circ, correct_state, param_list, n_shots=2048):
    '''Inputs:
    circ: The circuit to be tested
    correct_state: The correct state for comparison
    param_list: The error model parameters, currently only [T2, t_cz]
    n_shots: Number of shots to average over
    '''
    T2, t_cz = param_list

    # Run the circuit
    results = execute(
        circ,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=T2, t_cz=t_cz),
        memory=True,
        shots=n_shots
    ).result()

    # Post-selection
    select_indices = select_no_errors(results.get_memory())
    select_count = np.sum(select_indices)
    post_selection = np.array(
        results.data()['snapshots']['statevector']['stabilizer_0']
        )[select_indices]

    # Analyze results
    data = np.zeros(n_shots)
    for j in range(select_count):
#        statevector = results.data()[
#            'snapshots']['statevector']['stabilizer_0'][j]
        statevector = post_selection[j]
        data[j] = state_fidelity(statevector, correct_state)
    fid = np.sum(data)/select_count
    print('Boop')
    return fid, data

# %% Analyze results
T2_list = np.arange(40, 81, 10)*1e3 # 40-80 mus
t_cz_list = np.arange(100,301, 50) # 100-300 ns
n_shots = 1024

#T2_data = np.zeros(len(T2_list))
fid_T2 = np.zeros(len(T2_list))
fid_t = np.zeros(len(t_cz_list))
T2_results_list = []
t_cz_results_list = []
for index in range(len(circuit_list)):

    t_cz = 200
    fid_T2 = np.zeros(len(T2_list))
    for i in range(len(T2_list)):
        param_list = [T2_list[i], t_cz]
        fid_T2[i], _ = get_fidelity_data(
            circ=circuit_list[index],
            correct_state=correct_state[index],
            param_list=param_list,
            n_shots=1024,
        )
    T2_results_list.append(fid_T2)
    

    T2 = 60e3
    fid_t = np.zeros(len(t_cz_list))
    for i in range(len(t_cz_list)):
        param_list = [T2, t_cz_list[i]]
        fid_t[i], _ = get_fidelity_data(
            circ=circuit_list[index],
            correct_state=correct_state[index],
            param_list=param_list,
            n_shots=1024,
        )
    t_cz_results_list.append(fid_t)
    print('booperz')
# %% Temporary plotting
fig, axs = plt.subplots(2, figsize=(14, 10))
ax1 = axs[0]
ax2 = axs[1]
for i in range(4):
    ax1.plot(T2_list*1e-3, T2_results_list[i], 'o-', label=str(i-1))
    ax2.plot(t_cz_list, t_cz_results_list[i], 'o-', label=str(i-1))
#ax1.plot(T2_list*1e-3, fid_T2, 'o-', label='No transpilation')
ax1.set_xlabel('T2 [$\mu$s]')
ax1.set_ylabel('Average fidelity')
ax1.set_title('Fidelity with varying T2, constant 2-qb gate time (200 ns)')
#ax1.set(ylim=(0.74, 0.96))
ax1.legend()
ax1.grid(linewidth=1)

ax2.set_xlabel('2-qb gate time [ns]')
ax2.set_ylabel('Average fidelity')
ax2.set_title('Fidelity with varying 2-qb gate time, constant T2 (60 $\mu$s)')
#ax2.set(ylim=(0.74, 0.96))
ax2.legend()
ax2.grid(linewidth=1)

# %% OLD VERSION
T2_list = np.arange(40, 81, 10)*1e3 # 40-80 mus
t_cz_list = np.arange(100,301, 50) # 100-300 ns
logical = logical_states()
log0 = DensityMatrix(logical[1])
n_shots = 1024

# Arrays for storing all the stuff
T2_data = np.zeros([len(T2_list), n_shots])
T2_data_t0 = np.zeros([len(T2_list), n_shots])
T2_data_t1 = np.zeros([len(T2_list), n_shots])
T2_data_t2 = np.zeros([len(T2_list), n_shots])
t_cz_data = np.zeros([len(t_cz_list), n_shots])
t_cz_data_t0 = np.zeros([len(t_cz_list), n_shots])
t_cz_data_t1 = np.zeros([len(t_cz_list), n_shots])
t_cz_data_t2 = np.zeros([len(t_cz_list), n_shots])

# No transpilation, vary T2, fixed t_cz (WITH POST SELECTION)
fid_T2 = np.zeros(len(T2_list))
for i in range(len(fid_T2)):
    T2 = T2_list[i]

    # Run the circuit
    results = execute(
        circ,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=T2, t_cz=200),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        partial_sv = partial_trace(statevector, [5,6])
        T2_data[i][j] = state_fidelity(log0, partial_sv)
fid_T2 = np.sum(T2_data, axis=1)/n_shots
print('Finished varying T2 without transpilation')

# No transpilation, vary t_cz, fixed T2 (NO POST SELECTING HERE AND BELOW)
fid_cz = np.zeros(len(t_cz_list))
for i in range(len(fid_cz)):
    t_cz = t_cz_list[i]

    # Run the circuit
    results = execute(
        circ,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=60e3, t_cz=t_cz),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        partial_sv = partial_trace(statevector, [5,6])
        t_cz_data[i][j] = state_fidelity(log0, partial_sv)
fid_cz = np.sum(t_cz_data, axis=1)/n_shots
print('Finished varying t_cz without transpilation')

# With transpilation 0, vary T2, fixed t_cz
fid_T2_t0 = np.zeros(len(T2_list))
for i in range(len(fid_T2)):
    T2 = T2_list[i]

    # Run the circuit
    results = execute(
        circ_t0,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=T2, t_cz=200),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        T2_data_t0[i][j] = state_fidelity(logical_t0, statevector)
fid_T2_t0 = np.sum(T2_data_t0, axis=1)/n_shots
print('Finished varying T2 with transpilation 0')

# With transpilation, vary t_cz, fixed T2
fid_cz_t0 = np.zeros(len(t_cz_list))
for i in range(len(fid_cz)):
    t_cz = t_cz_list[i]

    # Run the circuit
    results = execute(
        circ_t0,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=60e3, t_cz=t_cz),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        t_cz_data_t0[i][j] = state_fidelity(logical_t0, statevector)
fid_cz_t0 = np.sum(t_cz_data_t0, axis=1)/n_shots
print('Finished varying t_cz with transpilation 0')
#===========================================================================
# With transpilation 1, vary T2, fixed t_cz
fid_T2_t1 = np.zeros(len(T2_list))
for i in range(len(fid_T2)):
    T2 = T2_list[i]

    # Run the circuit
    results = execute(
        circ_t1,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=T2, t_cz=200),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        T2_data_t1[i][j] = state_fidelity(logical_t1, statevector)
fid_T2_t1 = np.sum(T2_data_t1, axis=1)/n_shots
print('Finished varying T2 with transpilation 1')

# With transpilation 1, vary t_cz, fixed T2
fid_cz_t1 = np.zeros(len(t_cz_list))
for i in range(len(fid_cz)):
    t_cz = t_cz_list[i]

    # Run the circuit
    results = execute(
        circ_t1,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=60e3, t_cz=t_cz),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        t_cz_data_t1[i][j] = state_fidelity(logical_t1, statevector)
fid_cz_t1 = np.sum(t_cz_data_t1, axis=1)/n_shots
print('Finished varying t_cz with transpilation 1')
#==========================================================================
# With transpilation 2, vary T2, fixed t_cz
fid_T2_t2 = np.zeros(len(T2_list))
for i in range(len(fid_T2)):
    T2 = T2_list[i]

    # Run the circuit
    results = execute(
        circ_t2,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=T2, t_cz=200),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        T2_data_t2[i][j] = state_fidelity(logical_t2, statevector)
fid_T2_t2 = np.sum(T2_data_t2, axis=1)/n_shots
print('Finished varying T2 with transpilation 2')

# With transpilation 2, vary t_cz, fixed T2
fid_cz_t2 = np.zeros(len(t_cz_list))
for i in range(len(fid_cz)):
    t_cz = t_cz_list[i]

    # Run the circuit
    results = execute(
        circ_t2,  
        Aer.get_backend('qasm_simulator'),
        noise_model=thermal_relaxation_model(T2=60e3, t_cz=t_cz),
        shots=n_shots
    ).result()
    counts = results.get_counts()

    # Analyze results
    for j in range(n_shots):
        statevector = results.data()['snapshots']['statevector']['stabilizer_0'][j]
        t_cz_data_t2[i][j] = state_fidelity(logical_t2, statevector)
fid_cz_t2 = np.sum(t_cz_data_t2, axis=1)/n_shots
print('Finished varying t_cz with transpilation 2')

# %% Loading data files
T2_data = np.load('data/T2_data.npy')
T2_data_t0 = np.load('data/T2_data_t0.npy')
T2_data_t1 = np.load('data/T2_data_t1.npy')
T2_data_t2 = np.load('data/T2_data_t2.npy')
t_cz_data = np.load('data/t_cz_data.npy')
t_cz_data_t0 = np.load('data/t_cz_data_t0.npy')
t_cz_data_t1 = np.load('data/t_cz_data_t1.npy')
t_cz_data_t2 = np.load('data/t_cz_data_t2.npy')


# %% Plotting
fig, axs = plt.subplots(2, figsize=(14, 10))
ax1 = axs[0]
ax2 = axs[1]

# Vary T2
ax1.plot(T2_list*1e-3, fid_T2, 'o-', label='No transpilation')
ax1.plot(T2_list*1e-3, fid_T2_t0, 'o-', label='Transpiled 0')
ax1.plot(T2_list*1e-3, fid_T2_t1, 'o-', label='Transpiled 1')
#ax1.plot(T2_list*1e-3, fid_T2_t2, 'o-', label='Transpiled 2')
ax1.set_xlabel('T2 [$\mu$s]')
ax1.set_ylabel('Average fidelity')
ax1.set_title('Fidelity with varying T2, constant 2-qb gate time (200 ns)')
#ax1.set(ylim=(0.74, 0.96))
ax1.legend()
ax1.grid(linewidth=1)

# Vary t_cz
ax2.plot(t_cz_list, fid_cz, 'o-', label='No transpilation')
ax2.plot(t_cz_list, fid_cz_t0, 'o-', label='Transpiled 0')
ax2.plot(t_cz_list, fid_cz_t1, 'o-', label='Transpiled 1')
#ax2.plot(t_cz_list, fid_cz_t2, 'o-', label='Transpiled 2')
ax2.set_xlabel('2-qb gate time [ns]')
ax2.set_ylabel('Average fidelity')
ax2.set_title('Fidelity with varying 2-qb gate time, constant T2 (60 $\mu$s)')
#ax2.set(ylim=(0.74, 0.96))
ax2.legend()
ax2.grid(linewidth=1)
