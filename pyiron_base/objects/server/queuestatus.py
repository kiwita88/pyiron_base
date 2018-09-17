# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import subprocess
import pandas
import time
from pyiron_base.core.settings.generic import Settings
from pyiron_base.objects.job.generic import GenericJob
from pyironbase.objects.server.scheduler.generic import QUEUE_SCRIPT_PREFIX, QUEUE_SCRIPT_SUFFIX

"""
Set of functions to interact with the queuing system directly from within pyiron - optimized for the Sun grid engine.
"""

__author__ = "Jan Janssen"
__copyright__ = "Copyright 2017, Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department"
__version__ = "1.0"
__maintainer__ = "Jan Janssen"
__email__ = "janssen@mpie.de"
__status__ = "production"
__date__ = "Sep 1, 2017"

s = Settings()


def queue_table(job_ids=[], project_only=True):
    """
    Display the queuing system table as pandas.Dataframe

    Args:
        job_ids (list): check for a specific list of job IDs - empty list by default
        project_only (bool): Query only for jobs within the current project - True by default

    Returns:
        pandas.DataFrame: Output from the queuing system - optimized for the Sun grid engine
    """
    if project_only and not job_ids:
        return []
    output = subprocess.check_output(['qstat', '-u', str(s.login_user)], stderr=subprocess.STDOUT,
                                     universal_newlines=True).split('\n')
    if not output == ['']:
        job_dict_lst = []
        job_title = output[0].split()
        for line in output[2:]:
            job = line.split()
            while not len(job_title) == len(job):
                job.append('')
            try:
                in_list = int(job[2].split('_')[1].split('.')[0]) in job_ids
            except (IndexError, ValueError):
                in_list = False
            if (project_only and in_list) or not project_only:
                job_dict_lst.append(dict(zip(job_title, job)))
        if project_only:
            return pandas.DataFrame(job_dict_lst)
        else:
            return pandas.DataFrame(job_dict_lst[:-1])
    else:
        return None


def queue_id_table(requested_id=None):
    """
    Display the queuing system table as dictionary

    Args:
        requested_id (int): query for a specific job_id - optional

    Returns:
        dict: Dictionary with the output from the queuing system - optimized for the Sun grid engine
    """
    output = subprocess.check_output(['qstat', '-u', str(s.login_user)], stderr=subprocess.STDOUT,
                                     universal_newlines=True).split('\n')
    if not output == ['']:
        jobs_dict = {}
        for line in output[2:]:
            job = line.split()
            if len(job) > 4 and job[2].startswith(QUEUE_SCRIPT_PREFIX):
                job_id = job[2].split(QUEUE_SCRIPT_SUFFIX)[0].split(QUEUE_SCRIPT_PREFIX)[1]
                job_status = job[4]
                jobs_dict[job_id] = (int(job[0]), job_status)
                if requested_id is not None and job_id == requested_id:
                    return {job_id: (int(job[0]), job_status)}
        return jobs_dict
    else:
        return {}


def queue_info_by_job_id(job_id):
    """
    Display the queuing system info of job by qstat | grep  shell command
    as dictionary

    Args:
        requested_id (int): query for a specific job_id

    Returns:
        dict: Dictionary with the output from the queuing system - optimized for the Sun grid engine
    """
    # qstat with detailed information (Full jobname)
    proc1 = subprocess.Popen(
        ['qstat', '-u', str(s.login_user), '-r'], stdout=subprocess.PIPE)
    # grep by full job name and return one line before (-B1 flag)
    proc2 = subprocess.Popen(
        [
            'grep', '{prefix}{job_id}{suffix}'.format(
                prefix=QUEUE_SCRIPT_PREFIX,
                suffix=QUEUE_SCRIPT_SUFFIX,
                job_id=job_id),
            '-B1'
        ],
        stdin=proc1.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True)

    proc1.stdout.close()  # Allow proc1 to receive a SIGPIPE if proc2 exits.
    out, err = proc2.communicate()
    if out:
        summary_line, _ = out.split("\n")[:2]
        # summary_line=['QUE_ID', 'PRIORITY', 'FIXED_LENGTH_JOBNAME', 'USERNAME', 'QUEUESTATUS', 'DATE', 'TIME', 'CORES']
        qid, priority, _, user, job_status = summary_line.split()[:5]
        return {job_id: (int(qid), job_status)}
    else:
        return None

    
def queue_is_empty():
    """
    Check if the queue table is currently empty - no more jobs to wait for.

    Returns:
        bool: True if the table is empty, else False - optimized for the Sun grid engine
    """
    output = subprocess.check_output(['qstat', '-u', str(s.login_user)], stderr=subprocess.STDOUT,
                                     universal_newlines=True).split('\n')
    if output == ['']:
        return True
    else:
        return False


def queue_delete_job(item):
    """
    Delete a job from the queuing system

    Args:
        item (int, GenericJob): Provide either the job_ID or the full hamiltonian

    Returns:
        str: Output from the queuing system as string - optimized for the Sun grid engine
    """
    que_id = _validate_que_request(item)
    output = subprocess.check_output(['qdel', str(que_id)], stderr=subprocess.STDOUT, universal_newlines=True)
    return output


def queue_enable_reservation(item):
    """
    Enable a reservation for a particular job within the queuing system

    Args:
        item (int, GenericJob): Provide either the job_ID or the full hamiltonian

    Returns:
        str: Output from the queuing system as string - optimized for the Sun grid engine
    """
    que_id = _validate_que_request(item)
    output = subprocess.check_output(['qalter', '-R', 'y', str(que_id)], stderr=subprocess.STDOUT, universal_newlines=True)
    return output


def queue_report(item):
    """
    Detailed reporting for a particular job - using the qacct command of the sun grid engine.

    Args:
        item (int, GenericJob): Provide either the job_ID or the full hamiltonian

    Returns:
        pandas.DataFrame: Detailed report returned from the queuing system - optimized for the Sun grid engine
    """
    que_id = _validate_que_request(item)
    try:
        output = subprocess.check_output(['qacct', '-o', str(s.login_user), '-j', str(que_id)],
                                         stderr=subprocess.STDOUT, universal_newlines=True).split('\n')
        return pandas.DataFrame(
            [[line.split()[0], line.split()[1:]] for line in output[1:]])
    except subprocess.CalledProcessError:
        pass


def queue_job_info(item):
    """
    Short reporting for a particular job - using the qstat command of the sun grid engine.

    Args:
        item (int, GenericJob): Provide either the job_ID or the full hamiltonian

    Returns:
        pandas.DataFrame: Short report returned from the queuing system - optimized for the Sun grid engine
    """
    que_id = _validate_que_request(item)
    try:
        output = subprocess.check_output(['qstat', '-j', str(que_id)], stderr=subprocess.STDOUT,
                                         universal_newlines=True).split('\n')
        return pandas.DataFrame(
            [[line_arg.replace('  ', '') for line_arg in line.split(': ')] for line in output[1:]][0:24])
    except subprocess.CalledProcessError:
        pass


def wait_for_job(job, interval_in_s=5, max_iterations=100):
    """
    Sleep until the job is finished but maximum interval_in_s * max_iterations seconds.

    Args:
        job (GenericJob): Job to wait for
        interval_in_s (int): interval when the job status is queried from the database - default 5 sec.
        max_iterations (int): maximum number of iterations - default 100
    """
    for _ in range(max_iterations):
        job.refresh_job_status()
        if job.status.finished or job.status.aborted:
            break
        time.sleep(interval_in_s)


def _validate_que_request(item):
    """
    Internal function to convert the job_ID or hamiltonian to the queuing system ID.

    Args:
        item (int, GenericJob): Provide either the job_ID or the full hamiltonian

    Returns:
        int: queuing system ID
    """
    if isinstance(item, int):
        que_id = item
    elif isinstance(item, GenericJob):
        if item.server.queue_id:
            que_id = item.server.queue_id
        else:
            raise ValueError('This job does not have a queue ID.')
    else:
        raise TypeError('The queue can either query for IDs or for pyiron GenericJobObjects.')
    return que_id
