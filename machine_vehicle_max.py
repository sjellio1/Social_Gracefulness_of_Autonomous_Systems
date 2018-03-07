from constants import CONSTANTS as C
import numpy as np
import scipy
from scipy import optimize
# from keras.models import load_model


class MachineVehicle:

    """
    States:
            X-Position
            Y-Position
    """

    def __init__(self, machine_initial_state, human_initial_state):

        self.machine_theta = C.MACHINE_INTENT

        self.machine_states = [machine_initial_state]
        self.machine_actions = []

        self.human_states = [human_initial_state]
        self.human_actions = []
        self.human_predicted_states = [human_initial_state]

        self.human_predicted_theta = C.HUMAN_INTENT

        self.human_predicted_state = human_initial_state

        # self.action_prediction_model = load_model('nn/action_prediction_model.h5')

        self.debug_1 = 0
        self.debug_2 = 0
        self.debug_3 = 0

        t_steps = C.T_FUTURE
        theta_self = C.MACHINE_INTENT
        theta_other = C.HUMAN_INTENT
        self.previous_a_self = np.tile((theta_self[1] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER,
                       theta_self[2] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER),
                      (t_steps, 1))
        self.previous_a_other = np.tile((theta_other[1] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER,
                               theta_other[2] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER),
                              (t_steps, 1))

    def get_state(self):
        return self.machine_states[-1]

    def update(self, human_state):

        """ Function ran on every frame of simulation"""

        ########## Update human characteristics here ########

        machine_theta = C.MACHINE_INTENT  # ?????

        if len(self.human_states) > C.T_PAST:
            human_predicted_theta = self.get_human_predicted_intent()

            self.human_predicted_theta = human_predicted_theta


        ########## Calculate machine actions here ###########

        # Use prediction function
        [machine_actions, human_predicted_actions] = self.get_actions(self.human_states[-1], self.machine_states[-1],
                                                                        self.human_predicted_theta, self.machine_theta, C.T_FUTURE)

        # Use prediction model
        # [machine_actions, human_predicted_actions] = self.get_learned_action(self.human_states[-1], self.machine_states[-1],
        #                                                                self.human_theta, self.machine_theta, C.T_FUTURE)


        self.human_predicted_state = human_state + sum(human_predicted_actions)

        self.update_state_action(machine_actions)

        last_human_state = self.human_states[-1]
        self.human_states.append(human_state)
        self.human_actions.append(np.array(human_state)-np.array(last_human_state))

    def update_state_action(self, actions):

        # Restrict speed
        action_x = np.clip(actions[0][0], -C.VEHICLE_MOVEMENT_SPEED, C.VEHICLE_MOVEMENT_SPEED)
        action_y = np.clip(actions[0][1], -C.VEHICLE_MOVEMENT_SPEED, C.VEHICLE_MOVEMENT_SPEED)

        self.machine_states.append(np.add(self.machine_states[-1], (action_x, action_y)))
        self.machine_actions.append((action_x, action_y))

    def get_actions(self, s_other, s_self, theta_other, theta_self, t_steps):

        """ Function that accepts 2 vehicles states, intents, criteria, and an amount of future steps
        and return the ideal actions based on the loss function"""

        # Initialize actions
        # actions_other = np.array([0 for _ in range(2 * t_steps)])
        # actions_self = np.array([0 for _ in range(2 * t_steps)])
        actions_other = np.reshape(self.previous_a_other, 2 * t_steps)
        actions_self = np.reshape(self.previous_a_self, 2 * t_steps)

        bounds = []
        for _ in range(t_steps):
            bounds.append((-C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER, C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER))
        for _ in range(t_steps):
            bounds.append((-C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER, C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER))

        A = np.zeros((t_steps, t_steps))
        A[np.tril_indices(t_steps, 0)] = 1

        cons_other = []
        for i in range(t_steps):
            cons_other.append({'type': 'ineq',
                               'fun': lambda x, i=i: s_other[1] + sum(x[t_steps:t_steps+i+1]) - C.Y_MINIMUM})
            cons_other.append({'type': 'ineq',
                               'fun': lambda x, i=i: -s_other[1] - sum(x[t_steps:t_steps+i+1]) + C.Y_MAXIMUM})

        cons_self = []
        for i in range(t_steps):
            cons_self.append({'type': 'ineq',
                              'fun': lambda x, i=i: s_self[1] + sum(x[t_steps:t_steps+i+1]) - C.Y_MINIMUM})
            cons_self.append({'type': 'ineq',
                              'fun': lambda x, i=i: -s_self[1] - sum(x[t_steps:t_steps+i+1]) + C.Y_MAXIMUM})

        loss_value = 0
        loss_value_old = loss_value + C.LOSS_THRESHOLD + 1
        iter_count = 0

        # Estimate machine actions
        optimization_results = scipy.optimize.minimize(self.loss_func, actions_self, bounds=bounds, constraints=cons_self,
                                                       args=(s_other, s_self, actions_other, theta_self))
        actions_self = optimization_results.x
        loss_value = optimization_results.fun

        # actions_self, actions_other = self.mpc_game(s_self, s_other, theta_self, theta_other, self.previous_a_self, self.previous_a_other)
        # self.previous_a_self = actions_self
        # self.previous_a_other = actions_other

        loss_value = optimization_results.fun

        while np.abs(loss_value-loss_value_old) > C.LOSS_THRESHOLD and iter_count < 1:
            loss_value_old = loss_value
            iter_count += 1

            # Estimate human actions
            optimization_results = scipy.optimize.minimize(self.loss_func, actions_other, bounds=bounds, constraints=cons_other,
                                                           args=(s_self, s_other, actions_self, theta_other))
            actions_other = optimization_results.x

            # Estimate machine actions
            optimization_results = scipy.optimize.minimize(self.loss_func, actions_self, bounds=bounds, constraints=cons_self,
                                                           args=(s_other, s_self, actions_other, theta_self))
            actions_self = optimization_results.x
            loss_value = optimization_results.fun

        actions_other = np.transpose(np.vstack((actions_other[:t_steps], actions_other[t_steps:])))
        actions_self = np.transpose(np.vstack((actions_self[:t_steps], actions_self[t_steps:])))

        self.previous_a_other = actions_other
        self.previous_a_self = actions_self

        return actions_self, actions_other

    def get_learned_action(self, s_other, s_self, s_desired_other, s_desired_self, t_steps):

        """ Function that predicts actions based upon loaded neural network """

        s_other_y_range = [0, 1]
        s_self_x_range = [-2, 2]
        s_self_y_range = [0, 1]
        s_desired_other_x_range = [-2, 2]
        s_desired_other_y_range = [0, 1]
        c_other_range = [20, 100]

        #  Normalize inputs
        s_other_y_norm = (s_other[1] - s_other_y_range[0]) / (s_other_y_range[1] - s_other_y_range[0])
        s_self_x_norm = (s_self[0] - s_self_x_range[0]) / (s_self_x_range[1] - s_self_x_range[0])
        s_self_y_norm = (s_self[1] - s_self_y_range[0]) / (s_self_y_range[1] - s_self_y_range[0])
        s_desired_other_x_norm = (s_desired_other[0] - s_desired_other_x_range[0]) / (s_desired_other_x_range[1] - s_desired_other_x_range[0])
        s_desired_other_y_norm = (s_desired_other[1] - s_desired_other_y_range[0]) / (s_desired_other_y_range[1] - s_desired_other_y_range[0])

        network_output = self.action_prediction_model.predict(np.array([[s_other_y_norm,
                                                                         s_self_x_norm,
                                                                         s_self_y_norm,
                                                                         s_desired_other_x_norm,
                                                                         s_desired_other_y_norm]]))

        actions_self = np.array(network_output[0:t_steps])
        actions_other = np.array(network_output[t_steps:])

        # Scale outputs
        actions_self = actions_self * (2 * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER) - (C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER)
        actions_other = actions_other * (2 * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER) - (C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER)

        return actions_self, actions_other

    @staticmethod
    def loss_func(actions, s_other, s_self, actions_other, theta_self):

        """ Loss function defined to be a combination of state_loss and intent_loss with a weighted factor c """

        t_steps = int(len(actions)/2)

        action_factor = C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER

        actions             = np.transpose(np.vstack((actions[:t_steps], actions[t_steps:])))
        actions_other       = np.transpose(np.vstack((actions_other[:t_steps], actions_other[t_steps:])))
        theta_vector        = np.tile((theta_self[1] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER,
                                       theta_self[2] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER),
                                      (t_steps, 1))

        A = np.zeros((t_steps, t_steps))
        A[np.tril_indices(t_steps, 0)] = 1

        # Define state loss
        state_loss = np.reciprocal(np.linalg.norm(s_self + np.matmul(A, actions) - s_other - np.matmul(A, actions_other), axis=1)+1e-12)

        # Define action loss
        intent_loss = np.square(np.linalg.norm(actions - theta_vector, axis=1))

        # Define effort loss
        # effort_loss = 10 * theta_self[3] * np.sum(np.square(actions))

        # return np.sum(state_loss) + theta_self[0] * np.sum(intent_loss) + effort_loss  # Return weighted sum
        return np.sum(state_loss) + theta_self[0] * np.sum(intent_loss) # Return weighted sum

    def get_human_predicted_intent(self):
        """ Function accepts initial conditions and a time period for which to correct the
        attributes of the human car """

        # machine_states = machine_states[-t_steps:]
        # human_states = human_states[-t_steps:]

        # bounds = [(0, 20), (-1, 1), (-1, 1), (0, 1)]
        #
        # optimization_results = scipy.optimize.minimize(self.human_loss_func,
        #                                                old_human_theta,
        #                                                bounds=bounds,
        #                                                args=(machine_states, human_states, machine_theta))
        # human_theta = optimization_results.x

        ###############################################################################################
        # Max attempt
        t_steps = C.T_PAST
        s_self = self.human_states[-t_steps:]
        s_other = self.machine_states[-t_steps:]
        a_self = self.human_actions[-t_steps:]
        a_other = self.machine_actions[-t_steps:]
        theta_self = self.human_predicted_theta
        theta_other = C.MACHINE_INTENT #TODO: assume human knows machine for now
        nstate = len(s_other) #number of states
        alpha_self = theta_self[0]
        alpha_other = theta_other[0]
        A = np.zeros((t_steps, t_steps))
        A[np.tril_indices(t_steps, 0)] = 1 #lower tri 1s
        B = np.zeros((t_steps, t_steps))
        for i in range(t_steps-1):
            B[i,range(i+1,t_steps)]= np.arange(t_steps-1-i,0,-1)
        B = B + np.transpose(B) + np.diag(np.arange(t_steps,0,-1))
        b = np.arange(t_steps,0,-1)
        phi_self = np.tile((theta_self[1] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER,
                               theta_self[2] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER),
                              (t_steps, 1))
        phi_other = np.tile((theta_other[1] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER,
                               theta_other[2] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER),
                              (t_steps, 1))

        D = np.sum((np.array(s_self)-np.array(s_other))**2, axis=1) + 1e-3 #should be t_steps by 1, add small number for numerical stability

        # compute big K
        K_self = -2/(D**3)*B
        ds = np.array(s_self)[0]-np.array(s_other)[0]
        c_self = np.dot(np.diag(-2/(D**3)), np.dot(np.expand_dims(b, axis=1), np.expand_dims(ds, axis=0))) + \
                 np.dot(np.diag(2/(D**3)), np.dot(B, a_other))
        w = np.dot(K_self, a_self)+c_self
        A = np.sum(a_self,axis=0)
        W = np.sum(w,axis=0)
        AW = np.diag(np.dot(np.transpose(a_self),w))
        AA = np.sum(np.array(a_self)**2,axis=0)
        theta = (AW*A+W*AA)/(-W*A+AW*t_steps+1e-6)
        bound_y = [0,1] - np.array(s_self)[-1,1]
        theta[1] = np.clip(theta[1], bound_y[0], bound_y[1])
        alpha = W/(t_steps*theta-A)
        alpha = np.mean(np.clip(alpha,0.,100.))
        human_theta = (1-C.LEARNING_RATE)*self.human_predicted_theta + C.LEARNING_RATE*np.hstack((alpha,theta))
        ###############################################################################################

        predicted_theta = human_theta

        return predicted_theta

    def human_loss_func(self, human_theta, machine_states, human_states, machine_theta):

        """ Loss function for the human correction defined to be the norm of the difference between actual actions and
        predicted actions"""

        t_steps = int(len(machine_states))

        actual_actions = np.diff(human_states, axis=0)
        predicted_actions = self.get_actions(machine_states[0], human_states[0], machine_theta, human_theta, t_steps - 1)
        predicted_actions_self = predicted_actions[0]

        difference = np.array(actual_actions) - np.array(predicted_actions_self)

        return np.linalg.norm(difference)

##########################################################################
    def mpc_game(self, s_self, s_other, theta_self, theta_other, a_self_ini, a_other_ini):

        """ A faster solver for equilibrium """
        nstate = len(s_other) #number of states
        naction = nstate #dimension of actions
        t_steps = C.T_FUTURE #time steps for planning
        alpha_self = theta_self[0]
        beta_self = theta_self[3]
        alpha_other = theta_other[0]
        beta_other = theta_other[3]
        A = np.zeros((t_steps, t_steps))
        A[np.tril_indices(t_steps, 0)] = 1 #lower tri 1s
        B = np.zeros((t_steps, t_steps))
        for i in range(t_steps-1):
            B[i,range(i+1,t_steps)]= np.arange(t_steps-1-i,0,-1)
        B = B + np.transpose(B) + np.diag(np.arange(t_steps,0,-1))
        b = np.arange(t_steps,0,-1)

        phi_self = np.tile((theta_self[1] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER,
                               theta_self[2] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER),
                              (t_steps, 1))
        phi_other = np.tile((theta_other[1] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER,
                               theta_other[2] * C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER),
                              (t_steps, 1))
        a_self = a_self_ini #initial guess
        a_other = a_other_ini #initial guess

        delta = 1
        tau = 0.5
        eta_self = 0.01
        eta_other = 0.01
        lam_left_self = np.zeros(t_steps)
        lam_right_self = np.zeros(t_steps)
        lam_left_other = np.zeros(t_steps)
        lam_right_other = np.zeros(t_steps)
        r_self = 1
        r_other = 1

        while delta>0.001:
            a_self_tmp = a_self
            a_other_tmp = a_other
            delta2 = 1
            count2 = 0
            while delta2>0.001 and count2<100:
                count2 += 1
                a_self_old = a_self
                a_other_old = a_other
                ds = np.array(s_self)-np.array(s_other)
                d_self = np.dot(A, a_self)
                d_other = np.dot(A, a_other)
                D = np.sum((ds+d_self-d_other)**2, axis=1) + 1e-3 #should be t_steps by 1, add small number for numerical stability

                lane_left_self = -(s_self[1] + np.dot(A,a_self[:,1]) + 0.01)
                lane_left_other = -(s_other[1] + np.dot(A,a_other[:,1]) + 0.01)
                lane_right_self = s_self[1] + np.dot(A,a_self[:,1]) - 1.01
                lane_right_other = s_other[1] + np.dot(A,a_other[:,1]) - 1.01

                grad_lane_left_self = -np.dot(np.transpose(A*(lane_left_self>0)), self.penalty_prime(lane_left_self))
                grad_lane_left_other = -np.dot(np.transpose(A*(lane_left_other>0)), self.penalty_prime(lane_left_other))
                grad_lane_right_self = np.dot(np.transpose(A*(lane_right_self>0)), self.penalty_prime(lane_right_self))
                grad_lane_right_other = np.dot(np.transpose(A*(lane_right_other>0)), self.penalty_prime(lane_right_other))

                # compute big K
                K_self = -2/(D**3)*B + alpha_self*np.eye(t_steps)
                K_other = -2/(D**3)*B + alpha_other*np.eye(t_steps)
                c_self = np.dot(np.diag(-2/(D**3)), np.dot(np.expand_dims(b, axis=1), np.expand_dims(ds, axis=0))) + \
                         np.dot(np.diag(2/(D**3)), np.dot(B, a_other))
                c_other = np.dot(np.diag(-2/(D**3)), np.dot(np.expand_dims(b, axis=1), -np.expand_dims(ds, axis=0))) + \
                          np.dot(np.diag(2/(D**3)), np.dot(B, a_self))

                # compute const
                const_self = alpha_self*phi_self - c_self
                const_self[:,1] += - np.dot(lam_left_self,A) - np.dot(lam_right_self,A) \
                                   -2./r_self*(grad_lane_left_self + grad_lane_right_self)
                const_other = alpha_other*phi_other - c_other
                const_other[:,1] += - np.dot(lam_left_other,A) - np.dot(lam_right_other,A) \
                                    -2./r_other*(grad_lane_left_other + grad_lane_right_other)

                # update actions
                sol_self = np.linalg.solve(K_self, const_self)
                sol_other = np.linalg.solve(K_other, const_other)
                da_self = sol_self - a_self_old
                da_other = sol_other - a_other_old
                # learning_rate = 0.001
                learning_rate = 0.1/np.max(np.abs(np.hstack((da_self,da_other))))
                a_self = (1-learning_rate)*a_self_old + learning_rate*sol_self
                a_other = (1-learning_rate)*a_other_old + learning_rate*sol_other

                a_self = np.clip(a_self, -C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER, C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER)
                a_other = np.clip(a_other, -C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER, C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER)

                delta2 = np.mean(np.abs(a_self-a_self_old))+np.mean(np.abs(a_other-a_other_old))

            # update augmented lagrangian
            hnorm_self = sum((lane_left_self*(lane_left_self>0))**2 + (lane_right_self*(lane_right_self>0))**2)
            if hnorm_self > eta_self:
                r_self *= tau
            else:
                lam_left_self += 2*lane_left_self*(lane_left_self>0)/r_self
                lam_right_self += 2*lane_right_self*(lane_right_self>0)/r_self
                eta_self *= 0.5

            hnorm_other = sum((lane_left_other*(lane_left_other>0))**2 + (lane_right_other*(lane_right_other>0))**2)
            if hnorm_other > eta_other:
                r_other *= tau
            else:
                lam_left_other += 2*lane_left_other*(lane_left_other>0)/r_other
                lam_right_other += 2*lane_right_other*(lane_right_other>0)/r_other
                eta_other *= 0.5

            delta = np.mean(np.abs(a_self-a_self_tmp))+np.mean(np.abs(a_other-a_other_tmp))

        a_self = np.clip(a_self, -C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER, C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER)
        a_other = np.clip(a_other, -C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER, C.VEHICLE_MOVEMENT_SPEED * C.ACTION_PREDICTION_MULTIPLIER)

        return a_self, a_other

    def penalty_prime(self,x):
        # return 100/(np.exp(100.*x)+2+np.exp(-100.*x)) #use large enough scale to make a sharp sigmoid
        return (x>0)*x