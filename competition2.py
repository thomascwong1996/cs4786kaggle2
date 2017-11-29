import numpy as np
import matplotlib.pyplot as plt
from hmmlearn import hmm
import Markov
from math import *
from sklearn.externals import joblib
import time
import pickle
from random import randint

############
# PLOTTING #
############

# Plot the bot movement based on labelled data
def plotBotMovement():
	labels = np.genfromtxt("../Label.csv", delimiter=',')

	locations = {}
	xVals, yVals = [], []
	for i in range(labels.shape[0]):
		run, step, x, y = labels[i, :]
		locations.setdefault(run, []).append((step, (x, y)))
		xVals.append(x+1.5)
		yVals.append(y+1.5)

	for key, val in locations.items():
		orderedVal = sorted(val, key=lambda x: x[0])
		locations[key] = orderedVal

	plt.plot(xVals, yVals, 'ro')
	plt.show()

# Plot the states that the labels are assigned to
# Currently supports up to HMM 16
def plotPredictedStates(predictedStates, centroidMapping=None, numStates=10):
	labels = np.genfromtxt("../Label.csv", delimiter=',')

	# Map each state to a distinct RGB color
	cmap = ['#ff1111', '#ff8b11', '#fff311', '#9bff11', '#11ff88', '#11f7ff', '#1160ff', '#7011ff', 
			'#ff11e7', '#ff114c', '#000000', '#723416', '#0bc68b', '#9003af', '#a5a4a5', '#1a87ba']
	cmap = cmap[:numStates]

	xVals = [[] for _ in range(numStates)]
	yVals = [[] for _ in range(numStates)]
	for label in labels:
		run, step, x, y = label
		nextState = int(predictedStates[int(run) - 1, int(step) - 1])
		xVals[nextState].append(x + 1.5)
		yVals[nextState].append(y + 1.5)

	for i in range(numStates):
		plt.scatter(xVals[i], yVals[i], color=cmap[i], marker='.')

	if centroidMapping:
		xCentroids, yCentroids = [], []
		for botCoord, topCoord in centroidMapping.values():
			botX, botY = botCoord
			topX, topY = topCoord
			xCentroids.extend([botX, topX])
			yCentroids.extend([botY, topY])

	plt.plot(xCentroids, yCentroids, 'wo')

	plt.plot([0, 2.5], [2.5, 0], linestyle='solid') 
	plt.show()

#################
# PREPROCESSING #
#################

# Create 6000 x 1000 location matrix from Labels.csv
# M[i][j] = (x, y) --> At Run i + 1 and Step j + 1, bot is a location (x, y)
def createLocationMatrix():
	labels = np.genfromtxt("../Label.csv", delimiter=',')
	M = np.zeros((6000, 1000), dtype = 'float32, float32')

	for i in range(labels.shape[0]):
		run, step, x, y = labels[i, :]
		M[int(run-1), int(step-1)] = (x, y)

	return M

# Create observations matrix from Observations.csv
# M[i][j] = Angle of bot to x-axis on Run i + 1 and Step j + 1
def createObservationMatrix():
	observations = np.genfromtxt("../Observations.csv", delimiter = ',')

	return observations

# Create the labels dictionary
# Dict format: {Run: [(Step1, (x1, y1)) ... ]}
def createLabelsDict():
	labels = np.genfromtxt("../Label.csv", delimiter=',')
	OM = createObservationMatrix()

	locations = {}
	for i in range(labels.shape[0]):
		run, step, x, y = labels[i, :]
		run, step = int(run), int(step)
		x, y = x + 1.5, y + 1.5 # Add alpha/beta offsets
		observation = OM[run-1, step-1]
		val = (step, (x, y), observation)

		if run in locations:
			if val not in locations[run]:
				locations[run].append(val)
		else:
			locations[run] = [val]

	for key, val in locations.items():
		orderedVal = sorted(val, key=lambda x: x[0])
		locations[key] = orderedVal

	return locations
 
# Create submission file using 4000 (x, y) predicted location points
def createSubmission(predLocations, k):
	with open('hmm%i_submission.csv' % k, 'wb') as f:
		f.write('Id,Value\n')

		for i, (x, y) in enumerate(predLocations):
			xLine = ','.join([str(i+6001)+'x', str(x-1.5)])
			yLine = ','.join([str(i+6001)+'y', str(y-1.5)])
			f.write(xLine + '\n')
			f.write(yLine + '\n')
			

#####################
# LOADING / WRITING #
#####################

# Load dictionary from pickle file
def loadDict(filename):
	with open(filename, 'r') as f:
		d = pickle.load(f)
		return d

# Write dictionary to pickle file
def writeDict(d, filename):
	with open(filename, 'w') as f:
		pickle.dump(d, f)

# Save a CSV file with labels sorted by run and step
def writeLabelSortedCSV():
	labels = np.genfromtxt("../Label.csv", delimiter=',')
	sortedLabels = np.zeros((600000, 4))
	a = labels[:, 0]
	b = labels[:, 1]

	indices = np.lexsort((b, a))
	for i, row in enumerate(indices):
		sortedLabels[i, :] = labels[indices[i]]

	print "saving"
	np.savetxt('../LabelSorted.csv', sortedLabels, fmt=['%i']*2 + ['%f']*2, delimiter=",")

# Write to CSV the 10000 x 1000 predicted states matrix
def writePredictedStatesCSV(k=10):
	model = joblib.load('hmm%i_diag.pkl' % k)
	predictedStates = getPredictedStates(model)
	np.savetxt('hmm%i_predicted_states.csv' % k, predictedStates, fmt='%i', delimiter=",")

# Load 10000 x 1000 predicted states matrix from CSV
def loadPredictedStatesCSV(k=10):
	predictedStates = np.genfromtxt("hmm%i_predicted_states.csv" % k, delimiter=',')

	return predictedStates

################
# CALCULATIONS #
################

# Calculate the (alpha, beta) offset values from original position
# alpha = beta = 1.5
def calculateAlphaBeta(x1, y1, x2, y2, theta1, theta2):
	# Calculate alpha
	alphaNum = (x2 * tan(theta2)) - (x1 * tan(theta1)) + y1 - y2
	alphaDen = tan(theta1) - tan(theta2)
	alpha =  alphaNum / alphaDen

	# Calculate beta
	beta = ((x1 + alpha) * (tan(theta1))) - y1

	return (alpha, beta)

# Calculate [(minX, minY), (maxX, maxY)] from labels
# [(minX, minY), (maxX, maxY)] = [(-1.3074, -1.2908), (1.328, 1.2674)]
def calculateMinMaxXY():
	labels = np.genfromtxt("../Label.csv", delimiter=',')

	minX, minY = float("inf"), float("inf")
	maxX, maxY = float("-inf"), float("-inf")
	for i in range(labels.shape[0]):
		label = labels[i]
		_, _, x, y = label
		minX, minY = min(x, minX), min(y, minY)
		maxX, maxY = max(x, maxX), max(y, maxY)

	minX, minY = round(minX, 4), round(minY, 4)
	maxX, maxY = round(maxX, 4), round(maxY, 4)

	return [(minX, minY), (maxX, maxY)]

# Use consecutive steps in runs to calculate average bot step size
# Avg step size = 0.15356177070436083
def calculateAverageStepSize():
	sortedLabels = np.genfromtxt("../LabelSorted.csv", delimiter=',')
	distances = []

	for i in range(1, sortedLabels.shape[0]):
		if sortedLabels[i-1, 0] == sortedLabels[i, 0]:
			if sortedLabels[i-1, 1] + 1 == sortedLabels[i, 1]:
				distances.append(np.linalg.norm(sortedLabels[i-1,2:]-sortedLabels[i,2:]))

	distances = np.array(distances)
	return np.mean(distances)

# Get the two centroids for each state 
def getStateCentroids(predictedStates, mapping, numStates=10):
	labels = np.genfromtxt("../Label.csv", delimiter=',')

	topStateCoords = [[] for _ in range(numStates)]
	botStateCoords = [[] for _ in range(numStates)]
	for label in labels:
		run, step, x, y = label
		nextState = predictedStates[int(run) - 1, int(step) - 1]
		mappedState = mapping[nextState]
		x, y = x + 1.5, y + 1.5

		# Division line: y = 2.5 - x
		if y > 2.5 - x: # Above line
			topStateCoords[mappedState].append((x, y))
		else: # Below line
			botStateCoords[mappedState].append((x, y))

	centroidMapping = {}

	for i in range(numStates):
		topCoords = topStateCoords[i]
		topX = np.mean(np.array([x for x, _ in topCoords]))
		topY = np.mean(np.array([y for _, y in topCoords]))

		botCoords = botStateCoords[i]
		botX = np.mean(np.array([x for x, _ in botCoords]))
		botY = np.mean(np.array([y for _, y in botCoords]))

		centroidMapping[i] = [(botX, botY), (topX, topY)]

	return centroidMapping

##############
# ALGORITHMS #
##############

# Run HMM with given k components and covariance type
# Also saves a pickle for future use
def runHMM(k, cov_type='diag'):
	observations = np.genfromtxt("../Observations.csv", delimiter = ',')

	print "Starting HMM"
	start_time = time.time()
	model = hmm.GaussianHMM(n_components=k, covariance_type=cov_type)
	X = observations.flatten().reshape(-1, 1)
	lengths = [1000] * 10000
	model.fit(X, lengths)
	print "Done running HMM"

	joblib.dump(model, "hmm%i_%s.pkl" % (k, cov_type))
	print("--- %s seconds ---" % (time.time() - start_time))

# Get predictions from model
def getPredictedStates(model):
	observations = np.genfromtxt("../Observations.csv", delimiter = ',')
	X = observations.flatten().reshape(-1, 1)
	predictedStates = model.predict(X)

	return np.reshape(predictedStates, (10000,1000))

def linearRegression():
	sortedLabels = np.genfromtxt("../LabelSorted.csv", delimiter=',')
	regr = linear_model.LinearRegression()
	x_train = []
	y_train = []
	x_train.append(993)
	x_train.append(999)
	x_train.append(1000)
	y_train.append((sortedLabels[297, 2], sortedLabels[297, 3]))
	y_train.append((sortedLabels[298,2], sortedLabels[298, 3]))
	y_train.append((sortedLabels[299, 2], sortedLabels[299, 3]))

	regr.fit(np.array(x_train).reshape(-1, 1), np.array(y_train).reshape(-1,1))

	y_pred = regr.predict(1001)
	print y_pred


def run():
	return
	# observations = np.genfromtxt("../Observations.csv", delimiter = ',')
	# writeLabelSortedCSV()

	# print "starting hmm"
	# start_time = time.time()
	# k = 20
	# model = hmm.GaussianHMM(n_components=k)
	# model.fit(observations)
	# print "done running hmm"
	# joblib.dump(model, "hmm"+str(k)+".pkl")
	# print("--- %s seconds ---" % (time.time() - start_time))
	# model = joblib.load("hmm20.pkl")
	# print model.predict(observations)
	# sortedLabels = np.genfromtxt("../LabelSorted.csv", delimiter=',')
	# x = np.array([993, 999, 1000])
	# y1 = np.array([sortedLabels[297, 2], sortedLabels[298, 2], sortedLabels[299,2]])
	# y2 = np.array([sortedLabels[297, 3], sortedLabels[298, 3], sortedLabels[299,3]])
	# A = np.vstack([x, np.ones(len(x))]).T

	# m1, c1 = np.linalg.lstsq(A, y1)[0]
	# m2, c2 = np.linalg.lstsq(A, y2)[0]

	# x = m1 * 1001 + c1
	# y = m2 * 1001 + c1
	# print x, y
	# # linearRegression()

# Get whether the last 4000 points are increasing or decreasing states
def getLast4000Direction(predictedStates, mapping):
	last4000last5 = np.zeros((4000, 5))
	last4000last5 = predictedStates[6000:,-5:]

	for i in range(last4000last5.shape[0]):
		for j in range(last4000last5.shape[1]):
			last4000last5[i, j] = mapping[last4000last5[i, j]]

	directions = [] # -1 for decreasing, 1 for increasing
	for last5 in last4000last5:
		directionFound = False
		for i in range(len(last5) - 1, 0, -1):
			if directionFound: continue

			prev, curr = last5[i-1], last5[i]
			if prev < curr:
				directions.append(1)
				directionFound = True
			elif prev > curr:
				directions.append(-1)
				directionFound = True

		if not directionFound:
			directions.append(1)

	return directions

# Write HMM 10 submission file
def hmm10():
	hmm10_pred_actual_mapping = {
		0: 3,
		1: 7,
		2: 1,
		3: 9,
		4: 5,
		5: 4,
		6: 6,
		7: 2,
		8: 8,
		9: 0
	}

	predictedStates = loadPredictedStatesCSV()
	centroidMapping = loadDict('hmm10_centroid_mapping.csv')

	last4000Direction = getLast4000Direction(predictedStates, hmm10_pred_actual_mapping)
	last4000States = predictedStates[6000:,-1]

	predLocations = []
	for state, direction in zip(last4000States, last4000Direction):
		botCoord, topCoord = centroidMapping[state]
		predLocation = topCoord if direction == 1 else botCoord
		predLocations.append(predLocation)

	createSubmission(predLocations)

# Write HMM 16 submission file
def hmm16():
	hmm16_pred_actual_mapping = {
		0: 1,
		1: 11,
		2: 6,
		3: 14,
		4: 9,
		5: 4,
		6: 13,
		7: 5,
		8: 10,
		9: 7,
		10: 0,
		11: 3,
		12: 12,
		13: 2,
		14: 15,
		15: 8
	}

	predictedStates = loadPredictedStatesCSV(16)
	centroidMapping = loadDict('hmm16_centroid_mapping.csv')

	last4000Direction = getLast4000Direction(predictedStates, hmm16_pred_actual_mapping)
	last4000States = predictedStates[6000:,-1]

	predLocations = []
	for state, direction in zip(last4000States, last4000Direction):
		botCoord, topCoord = centroidMapping[state]
		predLocation = topCoord if direction == 1 else botCoord
		predLocations.append(predLocation)

	createSubmission(predLocations, 16)

if __name__ == '__main__':
	np.set_printoptions(threshold=np.nan)

	hmm10_pred_actual_mapping = {
		0: 3,
		1: 7,
		2: 1,
		3: 9,
		4: 5,
		5: 4,
		6: 6,
		7: 2,
		8: 8,
		9: 0
	}

	predictedStates = loadPredictedStatesCSV()
	centroidMapping = loadDict('hmm10_centroid_mapping.csv')

	plotPredictedStates(predictedStates, centroidMapping, 10)











	


