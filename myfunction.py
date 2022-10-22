# -*- coding: utf-8 -*-
"""
Created on Fri May 29 09:25:14 2020
Defines MAVF (upper bound, weight, and scaling function) scenarios
@author: yxo2

#Scenario definition:

1) 2020RAMP: used for 2020RAMP. nonlinear scaling function.
2) MAVF_TURN_01: used for TURN scenario analysis.
    upper bound for safety attribute set to 1000
    weights the same as 2020RAMP
    breakpoints for nonlinear scaling function the same as before - 1EF, 10EF
        (note that this breakpoints are not 1% and 10% of the upper bound)
3) MAVF_TURN_02: linear scaling function for safety and financial attributes
    upperbound and weights are the same.
4) MAVF_TURN_03: combination of MAVF_TURN_01 and MAVF_TURN_02
5) 2022Alt2_UNCAPPED: testing Alt2 scenario for MAVF update

When MAVF Scenario name contains 'UNCAPPED' then the MAVF is uncapped at upperbound.
When MAVF Scenario name does not contain 'UNCAPPED' then the MAVF is capped at 100 at upperbound

"""
from scipy.interpolate import InterpolatedUnivariateSpline
import numpy as np
import pandas as pd
import sys



SCALER = 1000
ATTRIBUTES = ['Safety', 'Electric Reliability', 'Gas Reliability', 'Financial']
CONSEQ_MAP = {'Safety': 'Safety', 
              'Electric Reliability':'Electric Reliability',
              'Gas Reliability':'Gas Reliability', 
              'Financial':'Financial', 
              'Aggregated':'Aggregated'}
EF = 0.25  # equivalent fatality factor for serious injuries

def get_MAVF(mavf_scenario):
    if mavf_scenario in ['2020RAMP', 'MAVF_TURN_02', '2020RAMP_UNCAPPED', 'MAVF_TURN_02_UNCAPPED']:
        MAVF = pd.DataFrame(data=
            {'Upper Bound':  [100, 4*10**9, .75*10**6, 5*10**9],
            'Weight': [.50, .20, .05, .25]
            }, index = ATTRIBUTES)
    elif mavf_scenario in ['MAVF_TURN_01', 'MAVF_TURN_03', 'MAVF_TURN_01_UNCAPPED', 'MAVF_TURN_03_UNCAPPED']: 
        MAVF = pd.DataFrame(data=
            {'Upper Bound': [1000, 4*10**9, .75*10**6, 5*10**9],
            'Weight': [.50, .20, .05, .25]
            }, index = ATTRIBUTES)
    elif mavf_scenario in ['2022Alt2_UNCAPPED']:
        MAVF = pd.DataFrame(data=
            {'Upper Bound': [750, 2*10**9, .75*10**6, 4*10**9],
            'Weight': [.45, .30, .05, .20]
            }, index = ATTRIBUTES)
    elif mavf_scenario in ['TURN_78Q1', 'TURN_78Q1_UNCAPPED','TURN_78Q2', 'TURN_78Q2_UNCAPPED']:
        MAVF = pd.DataFrame(data=
            {'Upper Bound': [500, 4*10**9, .75*10**6, 5*10**9],
            'Weight': [.40, .24, .06, .30]
            }, index = ATTRIBUTES)
    else:    # 2020RAMP
        print('Error: Please double check MAVF scenario name.\n')
        sys.exit(1)
    
    return MAVF



def calc_core(mavf_scenario, natural_unit, attribute):
    """ Calculate CoRE values when natural unit and attribute name is given
    
    Arguments:
        mavf_scenario: name of MAVF Scenario
        natural_unit: numpy array of numeric values
        attribute: numpy array of strings
        
    Returns:
        core: np array of Attribute CoRE values
        
    """
    global SCALER
    MAVF = get_MAVF(mavf_scenario)
    w = MAVF['Weight'][attribute].values
    
    if len(natural_unit.shape) > 1: 
        w = w.reshape((w.shape[0], 1))
        
        
    scaled_unit = scaling(mavf_scenario, natural_unit, attribute) 
    core = SCALER * w * scaled_unit
    return core


def scaling(mavf_scenario, natural_unit, attribute, capped=True):
    """ Calculate scaled unit from natural unit
        
    Arguments:
        
        nu: numpy array of natural unit, last dimension is attribute
        ub: 1D numby array of upper bound 
        attribute: 1D numpy array of string (for the last dimension of nu)
            
    Returns:
        su: scaled unit (ranged 0 to 100 when nu ranges from 0 to ub)
        
    """
    
    MAVF = get_MAVF(mavf_scenario)
    if np.isscalar(natural_unit): natural_unit = np.array([natural_unit])   #making the same size
    
    if np.isscalar(attribute): attribute = np.tile(attribute, natural_unit.shape)
    ub = MAVF['Upper Bound'][attribute].values
   
    su = np.zeros(natural_unit.shape)
    
    if len(natural_unit.shape) > 1: ub = ub.reshape((ub.shape[0], 1))
    
    if '2020RAMP_LINEAR' in mavf_scenario: # this needs to come first than '2020RAMP' 
        su = natural_unit/ub*100
        
    elif '2020RAMP' in mavf_scenario:
        y1 = .1  
        y2 = 5
        x = natural_unit/ub*100   # putting natural unit in 0-100 scale. np array
        x1 = 1
        x2 = 10
        s1 = .1 # s1= y1/x1 = .1
        s2 = .99
        slope = (s2-s1)/(x2-x1)
        su = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
            
    elif 'MAVF_TURN_01' in mavf_scenario:
        idx = (attribute == 'Safety')
        if np.count_nonzero(idx) > 0:
            y1 = .01  # 1/10 of 2020RAMP value. 
            y2 = 0.5  # 1/10 of 2020RAMP value.            
            x1 = 1    # natural unit in 0-1000 scale (EF),   1
            x2 = 10   # natural unit in 0-1000 scale (EF)
            s1 = .01  # s1 = y1/x1 = 0.01/1
            s2 = .099 
            slope = (s2-s1)/(x2-x1)
            x = natural_unit[idx,...]/100*100   # putting natural unit in 0-1000 scale, np array 
            
            
            su[idx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 1000], [y2, 100], k=1)(x)
            
                
            ''' this part of the code used to compute c vector, used in other
            c_A1 = y1/(x1/1000)
            c_B0 = 0.5*slope
            c_B1 = 10 - 0.5*slope*2*0.001*1000**2
            c_B2 = 0.5*slope*1000**2
            c_C0 = -(100-0.5)/(1-0.01)*(0.01)+0.5
            c_C1 = (100-0.5)/(1-0.01)
            c_D0 = 100
            c = (c_A1, c_B0,         c_B1,         c_B2,        c_C0,         c_C1,        c_D0)
            '''
        nidx = (attribute != 'Safety')    
        if np.count_nonzero(nidx) > 0:
            y1 = .1  
            y2 = 5
            
            x = natural_unit[nidx,...]/ub[nidx,...]*100   # putting natural unit in 0-100 scale
            x1 = 1
            x2 = 10
            s1 = .1
            s2 = .99
            slope = (s2-s1)/(x2-x1) 
            
            su[nidx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
                        
                
                
    elif 'MAVF_TURN_02' in mavf_scenario or 'MAVF_TURN_03' in mavf_scenario or 'TURN_78Q2' in mavf_scenario:
        idx = (attribute == 'Safety') + (attribute == 'Financial')
        if np.count_nonzero(idx) > 0: # safety & financial  
            su[idx,...] = natural_unit[idx,...]/ub[idx]*100
        
        nidx = (attribute == 'Electric Reliability') + (attribute == 'Gas Reliability')
        if np.count_nonzero(nidx) > 0: # reliability 
            y1 = .1  
            y2 = 5
            x = natural_unit[nidx,...]/ub[nidx,...]*100   # putting natural unit in 0-100 scale
            x1 = 1
            x2 = 10
            s1 = .1
            s2 = .99
            slope = (s2-s1)/(x2-x1) 
            su[nidx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
    
    elif '2022Alt2' in mavf_scenario:
        idx = (attribute == 'Safety')
        if np.count_nonzero(idx) > 0:
            y1 = .1*10/75  # 100/750 of 2020RAMP value. 
            y2 = 5*10/75  # 100/750 of 2020RAMP value.            
            x1 = 1/750*100    # natural unit in 0-750 scale (EF)
            x2 = 10/750*100   # natural unit in 0-750 scale (EF)
            s1 = y1/x1  # s1 = y1/x1 = y1
            s2 = .99 #### need to revisit and modify!!!!
            slope = (s2-s1)/(x2-x1)
            x = natural_unit[idx,...]/ub[idx,...]*100   # putting natural unit in 0-1000 scale, np array 
            
            
            su[idx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
            
                
            ''' this part of the code used to compute c vector, used in other
            c_A1 = y1/(x1/1000)
            c_B0 = 0.5*slope
            c_B1 = 10 - 0.5*slope*2*0.001*1000**2
            c_B2 = 0.5*slope*1000**2
            c_C0 = -(100-0.5)/(1-0.01)*(0.01)+0.5
            c_C1 = (100-0.5)/(1-0.01)
            c_D0 = 100
            c = (c_A1, c_B0,         c_B1,         c_B2,        c_C0,         c_C1,        c_D0)
            '''
        idx = (attribute == 'Electric Reliability')
        if np.count_nonzero(idx) > 0:
            y1 = .1*4/2  # 4/2 of 2020RAMP value. 
            y2 = 5*4/2  # 4/2 of 2020RAMP value.            
            x1 = 40/20   # 40M CMI out of 2B CMI
            x2 = 400/20   # 400M CMI out of 2B CMI
            s1 = y1/x1  # s1 = y1/x1 = y1
            s2 = .99 #### need to revisit and modify!!!!
            slope = (s2-s1)/(x2-x1)
            x = natural_unit[idx,...]/ub[idx,...]*100   # putting natural unit in 0-1000 scale, np array 
            
            
            su[idx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
                            
        idx = (attribute == 'Financial')
        if np.count_nonzero(idx) > 0:
            y1 = .1*5/4  # 100/750 of 2020RAMP value. 
            y2 = 5*5/4  # 100/750 of 2020RAMP value.            
            x1 = 50/40    # natural unit in 0 to 100 scale
            x2 = 500/40   # natural unit in 0 to 100 scale
            s1 = y1/x1  # s1 = y1/x1 = y1
            s2 = .99 #### need to revisit and modify!!!!
            slope = (s2-s1)/(x2-x1)
            x = natural_unit[idx,...]/ub[idx,...]*100   # putting natural unit in 0-1000 scale, np array 
            
            
            su[idx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
                            
        nidx = (attribute == 'Gas Reliability')    
        if np.count_nonzero(nidx) > 0:
            y1 = .1  
            y2 = 5
            
            x = natural_unit[nidx,...]/ub[nidx,...]*100   # putting natural unit in 0-100 scale
            x1 = 1
            x2 = 10
            s1 = .1
            s2 = .99
            slope = (s2-s1)/(x2-x1) 
            
            su[nidx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)

    elif 'TURN_78Q1' in mavf_scenario:
        idx = (attribute == 'Safety')
        if np.count_nonzero(idx) > 0:
            y1 = .1*10/50  # 100/750 of 2020RAMP value. 
            y2 = 5*10/50  # 100/750 of 2020RAMP value.            
            x1 = 1/500*100    # natural unit in 0-750 scale (EF)
            x2 = 10/500*100   # natural unit in 0-750 scale (EF)
            s1 = y1/x1  # s1 = y1/x1 = y1
            s2 = .99 #### need to revisit and modify!!!!
            slope = (s2-s1)/(x2-x1)
            x = natural_unit[idx,...]/ub[idx,...]*100   # putting natural unit in 0-1000 scale, np array 
            
            
            su[idx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
            
        nidx = (attribute != 'Safety')    
        if np.count_nonzero(nidx) > 0:
            y1 = .1  
            y2 = 5
            
            x = natural_unit[nidx,...]/ub[nidx,...]*100   # putting natural unit in 0-100 scale
            x1 = 1
            x2 = 10
            s1 = .1
            s2 = .99
            slope = (s2-s1)/(x2-x1) 
            
            su[nidx,...] = (x <= x1) * (y1/x1) * x + (x > x1) * (x <= x2) * (s1*x + slope/2 * (x - x1)**2) + \
                            (x > x2) * InterpolatedUnivariateSpline([x2, 100], [y2, 100], k=1)(x)
            
    else: 
        print('Error: Please double check MAVF scenario name.\n')
        sys.exit(1)
        
    
    if "UNCAPPED" in mavf_scenario:
        return_value = su
    else: # capped
        return_value = np.clip(su, a_min=None, a_max=100)
        
    return return_value


   

        

