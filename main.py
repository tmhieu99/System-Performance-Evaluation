import simpy
import random
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from kneed import KneeLocator

import matplotlib.pyplot as plt
import matplotlib.lines as mlines

# Define parameters for the single queue M/M/1/n
LAMBDA = 2
MU     = 3
BUFFER = 1000
RHO    = LAMBDA/MU

# Simulation settings
SEED         = 2019
VERBOSE      = False
LOGGED       = True
PLOT         = True
REPLICATIONS = 4

INFINITE_TIME = 100000000
SIMULATION_TIME = 10000
POPULATION = 50000000
random.seed(SEED)

class Job:
    """Definition of a Job object in the queueing system

    Args:
        job_id (int):                   A unique ID of the job
        arrive_time (int):              The time that the job arrive
        service_time (int):             The time requires to serve the job
        
    Attributes:
        job_id (int):                   A unique ID of the job
        arrive_time (int):              The time that the job arrive
        service_time (int):             The time requires to serve the job

    """

    def __init__(self, job_id, arrive_time, service_time):
        self.job_id = job_id 
        self.arrive_time = arrive_time
        self.service_time = service_time 



class Server:
    """Definition of a Server object in the queueing system

    Args:
        log_id (int):                   The id of the destination log file
        env (simpy.core.Environment):   SimPy environment

    Attributes:
        log_id (int):                   The id of the destination log file
        jobs (list):                    The job queue
        is_sleeping (bool):             A flag to indicate whether the system is idling or not

    """

    def __init__(self, log_id, env):
        self.log_id = log_id
        self.jobs = []
        self.is_sleeping = None
        self.response_time = 0
        self.waiting_time = 0
        self.idle_time = 0
        env.process(self.serve(env))

    def serve(self, env):
        """Serve event of the single queue system

        The server serve the next job in the queue. This set the queue to busy after
        job.service_time unit of time when the job is done.

        Args:
            env (simpy.core.Environment): SimPy Environment

        """

        while True:
            if len(self.jobs) == 0:
                """ If queue is empty then stay idle until new job arrives """
                self.is_sleeping = env.process(self.wait(env))
                t1 = env.now
                yield self.is_sleeping
                self.idle_time += env.now - t1
            else:
                """ Otherwise, serve the next job in the queue """ 
                job = self.jobs.pop(0)
                self.waiting_time += env.now - job.arrive_time
                yield env.timeout(job.service_time)
                self.response_time += env.now - job.arrive_time

    def wait(self, env):
        """Wait event of the single queue system

        The single queue system wait forever until a new job arrives

        Args:
            env (simpy.core.Environment): SimPy Environment

        """

        try:
            if (VERBOSE):
                print('Server is idle at %d' % env.now)
            yield env.timeout(INFINITE_TIME)
        except simpy.Interrupt as i:
            if (VERBOSE):
                print('A new job comes. Server waken up and works now at %d' % env.now)



class JobGenerator:
    """A Job generator that generates Job with Poisson-distribution interarrival time
    and service time

    Args:
        log_id (int):                   The id of the destination log file
        env (simpy.core.Environment):   SimPy environment
        server (Server):                Server object
        max_jobs (int):                 System capacity i.e. maximum queue length
        lamb (float):                   Mean arrival rate
        mu (float):                     Mean service rate per server

    Attributes:
        log_id (int):                   The id of the destination log file
        env (simpy.core.Environment):   SimPy environment
        server (Server):                Server object
        max_jobs (int):                 System capacity i.e. maximum queue length
        lamb (float):                   Mean arrival rate
        mu (float):                     Mean service rate per server
        rejected_jobs (int):            Number of jobs that got rejected due to queue overload

    """

    def __init__(self, log_id, env, server, max_jobs, lamb = 0.1, mu = 0.1):
        self.log_id = log_id
        self.server = server
        self.max_jobs = max_jobs
        self.job_id = 0
        self.lamb = lamb
        self.mu = mu
        self.rejected_jobs = 0;
        env.process(self.generate_job(env))
        env.process(self.record(env))

    def generate_job(self, env):
        while True:
            interarrival_time = random.expovariate(self.lamb)
            yield env.timeout(interarrival_time)

            if len(self.server.jobs) < self.max_jobs:
                """ If queue is not full, push new job to the queue """
                service_time = random.expovariate(self.mu)
                self.server.jobs.append(Job(self.job_id, env.now, service_time))
                self.job_id += 1

                if not self.server.is_sleeping.triggered:
                    self.server.is_sleeping.interrupt('Wakie wakie!')
            else:
                """ If the queue is full, then the job is rejected """
                self.rejected_jobs += 1

    def record(self, env):
        while True:
            if (LOGGED):
                if (self.job_id != 0):
                    logs[self.log_id].write('%d,%d,%f,%f,%f,%f\n' % (
                        env.now,                                            # Time
                        len(self.server.jobs),                              # Queue Length
                        servers[self.log_id].response_time/self.job_id,     # Mean response time
                        servers[self.log_id].waiting_time/self.job_id,      # Mean waiting time
                        1-servers[self.log_id].idle_time/env.now,           # Utilization
                        1-self.rejected_jobs/self.job_id))                  # Reliability
                else:
                    logs[self.log_id].write('%d,%d,%f,%f,%f,%f\n' % (
                        env.now,                                            # Time
                        len(self.server.jobs),                              # Queue Length
                        0,                                                  # Mean response time
                        0,                                                  # Mean waiting time
                        0,                                                  # Utilization
                        1))                                                 # Reliability
                yield env.timeout(1)



# Open the log files
logs = []
if (LOGGED):
    for i in range(REPLICATIONS):
        logs.append(open('log'+str(SEED+i)+'.csv', 'w'))
        logs[i].write('Time,Queue Length,Mean Response Time,Mean Waiting Time,Utilization,Reliability\n')

# Create a simulation environment

envs = []
servers = []
job_generators = []
for i in range(REPLICATIONS):
    envs.append(simpy.Environment())
    servers.append(Server(i, envs[i]))
    job_generators.append(JobGenerator(i, envs[i], servers[i], BUFFER, LAMBDA, MU))

# Start the simulation
for i in range(REPLICATIONS):
    envs[i].run(until = SIMULATION_TIME)

# Close the log file
if (LOGGED):
    for i in range(REPLICATIONS):
        logs[i].close()

# Read log data file
dfs = []
for i in range(REPLICATIONS):
    dfs.append(pd.read_csv('log'+str(SEED+i)+'.csv'))

# Calculate analytical performance
n = RHO/(1-RHO) - ((BUFFER+1)*RHO**(BUFFER+1))/(1-RHO**(BUFFER+1))
nq = RHO/(1-RHO) - RHO*(1+BUFFER*RHO**(BUFFER))/(1 - RHO**(BUFFER+1))
pb = ((1-RHO)/(1-RHO**(BUFFER+1)))*RHO**(BUFFER)
er = n/(LAMBDA*(1-pb))
ew = nq/(LAMBDA*(1-pb))

# Print analytical performance
print('------------ Analytical Performance ------------')
print('Traffic intensity:                   %.2f' % (RHO))
print('Mean no. of jobs in the system:      %.2f' % (n))
print('Mean no. of jobs in the queue:       %.2f' % (nq))
print('Mean response time:                  %.2f' % (er))
print('Mean waiting time:                   %.2f' % (ew))
 
# Print simulation performance
print('------------ Simulation Performance ------------')
print('Traffic intensity:                   %.2f' % (1-servers[0].idle_time/SIMULATION_TIME))
print('Mean no. of jobs in the system:      %.2f' % (dfs[0]['Queue Length'].mean()))
print('Mean no. of jobs in the queue:       %.2f' % ((dfs[0]['Queue Length'] - 1).mean()))
print('Mean response time:                  %.2f' % (servers[0].response_time/job_generators[0].job_id))
print('Mean waiting time:                   %.2f' % (servers[0].waiting_time/job_generators[0].job_id))
print('System utilization:                  %.2f/%.2f' % (1-servers[0].idle_time/SIMULATION_TIME, RHO))
print('System reliability:                  %.2f' % (1-(job_generators[0].rejected_jobs/job_generators[0].job_id)))

# Plot results
if (PLOT):
    # Specify all available metrics
    metrics     = ['Queue Length', 'Mean Response Time', 'Mean Waiting Time', 'Utilization', 'Reliability']
    curves      = ['concave', 'concave', 'concave', 'concave', 'convex']
    directions  = ['increasing', 'increasing', 'increasing', 'increasing', 'decreasing']

    fig, axs = plt.subplots(5, 2)

    '''
    # Individual replications
    axs[0][0].set_title('Individual replications')
    for i in range(REPLICATIONS):
        sns.lineplot(x='Time', y=target_metric, data=dfs[i], ax=axs[0][0])
    '''

    for col in range(len(metrics)):
        # Mean accross replications
        #axs[0][col].set_title('Mean across replications')
        axs[0][0].set_title('Mean across replications')
        df_mean = pd.concat(tuple([df for df in dfs]))
        df_mean = df_mean.groupby('Time').sum().reset_index()
        df_mean[metrics[col]] /= REPLICATIONS
        sns.lineplot(x='Time', y=metrics[col], data=df_mean, ax=axs[col][0])
        df_mean.to_csv('mean.csv')
    
        # Mean of last n-L observations 
        #axs[1][0].set_title('Mean of last n-L observations')
        l = np.arange(SIMULATION_TIME)
        mean_nl = [df_mean[metrics[col]].tail(len(df_mean)-i).mean() for i in range(len(df_mean))]
        df_mean_nl = pd.DataFrame({'L':l, 'Mean n-L':mean_nl})
        #sns.lineplot(x='L', y='Mean n-L', data=df_mean_nl, ax=axs[1][0])
        df_mean_nl.to_csv('mean_nl.csv')
    
        # Relative change
        axs[0][1].set_title('Relative changes')
        mean = df_mean[metrics[col]].mean()
        relative_change = (mean_nl - mean)/mean
        df_relative_change = pd.DataFrame({'L':l, 'Relative change':relative_change})
        sns.lineplot(x='L', y='Relative change', data=df_relative_change, ax=axs[col][1])
    
        # Knee locator
        a = range(1, len(relative_change)+1)
        kn = KneeLocator(a, relative_change, curve = curves[i], direction = directions[i])
        ymin, ymax = axs[col][1].get_ybound()
        axs[col][1].plot([kn.knee, kn.knee], [ymin, ymax], linestyle = 'dashed', color = 'red')
     
        #print('Knee point is at L =                 %d' %(kn.knee))
    
    plt.show()
