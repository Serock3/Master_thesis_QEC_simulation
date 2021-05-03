# %%
import numpy as np
from simulator_program.data_analysis_tools import fidelity_from_scratch
from matplotlib import pyplot as plt
from qiskit.providers.aer.noise.errors.standard_errors import thermal_relaxation_error
from qiskit.quantum_info.operators.symplectic.pauli import Pauli
from qiskit.circuit.quantumregister import QuantumRegister
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.execute_function import execute
from qiskit import Aer
from simulator_program.stabilizers import add_snapshot_to_circuit, logical_states
from qiskit.quantum_info.states.measures import state_fidelity
# Settings to used across most configurations
n_cycles = 5
n_shots = 1


def get_idle_single_qubit(snapshot_times, snapshot_type='dm', T1=40e3, T2=60e3,
                          theta=0, phi=0, pauliop='Z'):
    """Generates a single qubit-circuit initialized in the |1> state with
    snapshots at given times

    Args:
        snapshot_times (dict): The times in the circuit to add snapshots.
        T1 (float): T1 thermal relaxation, given in ns.
        T2 (float): T2 relaxation, given in ns.

    Returns:
        circ: Qiskit circuit object of a single qubit, with snapshots at given
              times and thermal relaxation in between.
    """
    qb = QuantumRegister(1, 'qubit')
    circ = QuantumCircuit(qb)
    initial_state = np.cos(theta/2)*np.array((1,0)) + \
        np.exp(1j*phi)*np.sin(theta/2)*np.array((0,1))
    circ.set_density_matrix(initial_state)
    time_passed = 0
    for i, time in enumerate(snapshot_times):
        time_diff = time-time_passed
        if time_diff > 0:
            thrm_relax = thermal_relaxation_error(
                T1, T2, time_diff).to_instruction()
            # print(time_diff,T1)
            circ.append(thrm_relax, [qb[0]])
        add_snapshot_to_circuit(circ, snapshot_type, i, [
                                qb[0]], conditional=False, pauliop=pauliop)
        time_passed = time

    simulator = Aer.get_backend('aer_simulator')
    simulator.set_option('method', 'density_matrix')
    results = execute(circ, simulator,
                      noise_model=None, shots=n_shots).result()
    return results


def get_idle_encoded_513(snapshot_times, snapshot_type='dm', T1=40e3, T2=60e3,
                         theta=0, phi=0, pauliop='ZZZZZ'):
    logical_0, logical_1 = logical_states(include_ancillas=None)
    circ = QuantumCircuit(5)
    initial_state = np.cos(theta/2)*logical_0 + \
        np.exp(1j*phi)*np.sin(theta/2)*logical_1
    circ.set_density_matrix(initial_state)
    time_passed = 0
    for i, time in enumerate(snapshot_times):
        time_diff = time-time_passed
        if time_diff > 0:
            thrm_relax = thermal_relaxation_error(
                T1, T2, time_diff).to_instruction()
            for qubit in circ.qubits:
                circ.append(thrm_relax, [qubit])

        add_snapshot_to_circuit(circ, snapshot_type, i,
                                circ.qubits, conditional=False, pauliop=pauliop)
        time_passed = time

    simulator = Aer.get_backend('aer_simulator')
    simulator.set_option('method', 'density_matrix')
    results = execute(circ, simulator,
                      noise_model=None, shots=n_shots).result()
    return results


def project_dm_to_logical_subspace_V1(rho):
    P_L = 0
    logical = logical_states(include_ancillas=None)
    for i in range(2):
        P_L += logical[i] @ rho @ logical[i]
    rho_L = np.zeros((2, 2), dtype=complex)
    for i in range(2):
        for j in range(2):
            rho_L[i, j] = (logical[i] @ rho @ logical[j])/P_L
    return rho_L


def project_dm_to_logical_subspace_V2(rho):
    logical = logical_states(include_ancillas=None)
    # Projector to the code space
    I_L = np.outer(logical[0], logical[0])+np.outer(logical[1], logical[1])
    # Note here how the projector has to be included for this to work as expected
    logical_pauli_matrices = np.array((
        I_L,
        Pauli('XXXXX').to_matrix()@I_L,
        Pauli('YYYYY').to_matrix()@I_L,
        Pauli('ZZZZZ').to_matrix()@I_L
    ))

    P_L = np.trace(rho@logical_pauli_matrices[0])

    rho_L = np.zeros((2**5, 2**5), dtype=complex)
    for i in range(4):
        rho_L += logical_pauli_matrices[i] * \
            np.trace(rho@logical_pauli_matrices[i])/(2*P_L)
    return rho_L


def project_dm_to_logical_subspace_V3(rho):
    pauli_matrices = np.array((
        ((1, 0), (0, 1)),
        ((0, 1), (1, 0)),
        ((0, -1j), (1j, 0)),
        ((1, 0), (0, -1))
    ))
    logical = logical_states(include_ancillas=None)

    # Projector to the code space
    I_L = np.outer(logical[0], logical[0])+np.outer(logical[1], logical[1])
    # Note here how the projector has to be included for this to work as expected
    logical_pauli_matrices = np.array((
        I_L,
        Pauli('XXXXX').to_matrix()@I_L,
        Pauli('YYYYY').to_matrix()@I_L,
        Pauli('ZZZZZ').to_matrix()@I_L
    ))

    P_L = np.trace(rho@logical_pauli_matrices[0])

    rho_L = np.zeros((2, 2), dtype=complex)
    for i in range(4):
        rho_L += pauli_matrices[i] * \
            np.trace(rho@logical_pauli_matrices[i])/(2*P_L)
    return rho_L


# %% Expectation values and fid single qubit
T1 = 40e3
T2 = 60e3
n_datapoints = 100
times = np.linspace(0, 100e3, n_datapoints)
#%% Run single qubit
res_0 = get_idle_single_qubit(times, snapshot_type=['exp', 'dm'], T1=T1, T2=T2)
exp_0 = [res_0.data()['exp_'+str(index)]for index in range(n_datapoints)]
fid_0 = [state_fidelity([1, 0], res_0.data()['dm_'+str(index)])
         for index in range(n_datapoints)]
res_1 = get_idle_single_qubit(
    times, snapshot_type=['exp', 'dm'], theta=np.pi, T1=T1, T2=T2)
exp_1 = [res_1.data()['exp_'+str(index)]for index in range(n_datapoints)]
fid_1 = [state_fidelity([0, 1], res_1.data()['dm_'+str(index)])
         for index in range(n_datapoints)]
res_plus = get_idle_single_qubit(times, snapshot_type=[
                                 'exp', 'dm'], pauliop='X', theta=np.pi/2, T1=T1, T2=T2)
exp_plus = [res_plus.data()['exp_'+str(index)]for index in range(n_datapoints)]
fid_plus = [state_fidelity([1/np.sqrt(2), 1/np.sqrt(2)], res_plus.data()
                           ['dm_'+str(index)]) for index in range(n_datapoints)]
# %% plot exp values
fig, ax = plt.subplots(1, 1, figsize=(8, 6))
ax.plot(times, exp_0, label='<0|Z|0>')
ax.plot(times, exp_1, label='<1|Z|1>')
ax.plot(times, exp_plus, label='<+|X|+>')
ax.legend()
# %% plot fid values
fig, ax = plt.subplots(1, 1, figsize=(8, 6))
ax.plot(times, fid_0, 'b', label='|0>')
ax.plot(times, fid_1, 'r', label='|1>')
ax.plot(times, fid_plus, 'g', label='|+>')
ax.plot(times, np.exp(-times/T1), '--', label='exp(-t/T1) (|1>)')
ax.plot(times, 1/2+1/2 * np.exp(-times/T2),
        '--', label='1/2+1/2*exp(-t/T2) (|+>)')
ax.legend()
ax.set_xlabel('Time [ns]')
ax.set_ylabel('Probability of initial value')
# %% Expectation values and fid encoded qubit
res_0 = get_idle_encoded_513(times, snapshot_type=['exp', 'dm'], T1=T1, T2=T2)
exp_0 = [res_0.data()['exp_'+str(index)]for index in range(n_datapoints)]
fid_0 = [state_fidelity(logical_states(include_ancillas=None)[0], res_0.data()['dm_'+str(index)])
         for index in range(n_datapoints)]
fid_0_L = [state_fidelity([1, 0], project_dm_to_logical_subspace_V1(res_0.data()['dm_'+str(index)]))
           for index in range(n_datapoints)]
res_1 = get_idle_encoded_513(times, snapshot_type=['exp', 'dm'], T1=T1, T2=T2,theta=np.pi)
exp_1 = [res_1.data()['exp_'+str(index)]for index in range(n_datapoints)]
fid_1 = [state_fidelity(logical_states(include_ancillas=None)[1], res_1.data()['dm_'+str(index)])
         for index in range(n_datapoints)]
fid_1_L = [state_fidelity([0, 1], project_dm_to_logical_subspace_V1(res_1.data()['dm_'+str(index)]))
           for index in range(n_datapoints)]
res_plus = get_idle_encoded_513(times, snapshot_type=['exp', 'dm'], T1=T1, T2=T2, theta=np.pi/2)
exp_plus = [res_plus.data()['exp_'+str(index)]for index in range(n_datapoints)]
plus_L = (logical_states(include_ancillas=None)[0]+logical_states(include_ancillas=None)[1])/np.sqrt(2)
fid_plus = [state_fidelity(plus_L, res_plus.data()['dm_'+str(index)])
         for index in range(n_datapoints)]
fid_plus_L = [state_fidelity([1/np.sqrt(2), 1/np.sqrt(2)], project_dm_to_logical_subspace_V1(res_plus.data()['dm_'+str(index)]))
           for index in range(n_datapoints)]
# %% plot <Z>
fig, ax = plt.subplots(1, 1, figsize=(8, 6))
ax.plot(times, exp_0, label=r'$\langle 0_L|Z_L|0_L\rangle$')
ax.plot(times, exp_1, label=r'$\langle 1_L|Z_L|1_L\rangle$')
ax.plot(times, exp_plus, label=r'$\langle +_L|Z_L|+_L\rangle$')
ax.set_xlabel('Time [ns]')
ax.set_ylabel(r'Expectation value of $Z_L$')
ax.legend()
# %% plot <X>
res_0 = get_idle_encoded_513(times, snapshot_type=['exp'],pauliop='XXXXX', T1=T1, T2=T2)
exp_0 = [res_0.data()['exp_'+str(index)]for index in range(n_datapoints)]

res_1 = get_idle_encoded_513(times, snapshot_type=['exp'],pauliop='XXXXX', T1=T1, T2=T2,theta=np.pi)
exp_1 = [res_1.data()['exp_'+str(index)]for index in range(n_datapoints)]

res_plus = get_idle_encoded_513(times, snapshot_type=['exp'],pauliop='XXXXX', T1=T1, T2=T2, theta=np.pi/2)
exp_plus = [res_plus.data()['exp_'+str(index)]for index in range(n_datapoints)]
plus_L = (logical_states(include_ancillas=None)[0]+logical_states(include_ancillas=None)[1])/np.sqrt(2)

fig, ax = plt.subplots(1, 1, figsize=(8, 6))
ax.plot(times, exp_0, label=r'$\langle 0_L|X_L|0_L\rangle$')
ax.plot(times, exp_1, label=r'$\langle 1_L|X_L|1_L\rangle$')
ax.plot(times, exp_plus, label=r'$\langle +_L|X_L|+_L\rangle$')
ax.set_xlabel('Time [ns]')
ax.set_ylabel(r'Expectation value of $X_L$')
ax.legend()
# %% plot fid values
fig, ax = plt.subplots(1, 1, figsize=(8, 6))
ax.plot(times, fid_0, label=r'$|0_L\rangle$')
ax.plot(times, fid_1, label=r'$|1_L\rangle$')
ax.plot(times, fid_plus, label=r'$|+_L\rangle$')
ax.plot(times, fid_0_L, label=r'$|0_L\rangle$ projected')
ax.plot(times, fid_1_L, label=r'$|1_L\rangle$ projected')
ax.plot(times, fid_plus_L, label=r'$|+_L\rangle$ projected')
ax.plot(times, times*0+1/16, label=r'$1/16$')
ax.set_xlabel('Time [ns]')
ax.set_ylabel(r'Fidelity to initial state')
ax.legend()

# %% Test hypothesis of P_L * F_L = F_phys
res_0 = get_idle_encoded_513(times, snapshot_type=['dm'], T1=T1, T2=T2)
rho = res_0.data()['dm_'+str(20)]
logical = logical_states(include_ancillas=None)
I_L = np.outer(logical[0], logical[0])+np.outer(logical[1], logical[1])
logical_pauli_matrices = np.array((
    I_L,
    Pauli('XXXXX').to_matrix()@I_L,
    Pauli('YYYYY').to_matrix()@I_L,
    Pauli('ZZZZZ').to_matrix()@I_L
))
F_phys = state_fidelity(logical_states(include_ancillas=None)[0], rho)
P_L = np.trace(rho@logical_pauli_matrices[0])
F_L = state_fidelity([1, 0], project_dm_to_logical_subspace_V1(rho))
F_L_V2 = state_fidelity(logical_states(include_ancillas=None)[0], project_dm_to_logical_subspace_V2(rho))

print('P_L','*','F_L','=','F_phys','?')
print(P_L,'*',F_L,'=',F_phys)
print(np.abs(P_L*F_L-F_phys)<0.01)
# %%
