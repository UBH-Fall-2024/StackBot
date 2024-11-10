import datetime
import api_class
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from keras.api.models import Sequential
from keras.api.layers import Dense, LSTM


class StockPricePredictor:
    def __init__(self, time_steps=1, lstm_units=50, batch_size=1, epochs=10):
        """Initializes the StockPricePredictor object."""
        self.time_steps = time_steps
        self.lstm_units = lstm_units
        self.batch_size = batch_size
        self.epochs = epochs
        self.scaler_X = MinMaxScaler()
        self.scaler_y = MinMaxScaler()
        self.model = self._build_model()

    def _build_model(self):
        """Define and compile the LSTM model."""
        model = Sequential()
        model.add(LSTM(self.lstm_units, return_sequences=True,
                  input_shape=(self.time_steps, 11)))
        model.add(LSTM(self.lstm_units, return_sequences=False))
        model.add(Dense(25))
        model.add(Dense(1))
        model.compile(optimizer='adam', loss='mean_squared_error')
        return model

    def preprocess_data(self, data):
        """Prepares and scales data for LSTM training."""
        X = data.drop(columns=['close']).values
        y = data['close'].values
        X_scaled = self.scaler_X.fit_transform(X)
        y_scaled = self.scaler_y.fit_transform(y.reshape(-1, 1))
        # Reshape to 3D for LSTM
        X_scaled = X_scaled.reshape(
            (X_scaled.shape[0], self.time_steps, X_scaled.shape[1]))
        return X_scaled, y_scaled

    def fit(self, data):
        """Fits the model on the provided data."""
        X_scaled, y_scaled = self.preprocess_data(data)
        # self.model.fit(X_scaled, y_scaled, epochs=self.epochs,
        #                batch_size=self.batch_size)
        # Dictionary to store models and their losses
        self.model_history = {}

        # Fit the model and store each epoch's model and loss
        for epoch in range(self.epochs):
            history = self.model.fit(X_scaled, y_scaled, epochs=epoch+1,
                                     batch_size=self.batch_size, verbose=0)
            loss = history.history['loss'][0]
            self.model_history[epoch] = {
                'model': self.model.get_weights(), 'loss': loss}

        # Find the epoch with the lowest loss
        best_epoch = min(self.model_history,
                         key=lambda x: self.model_history[x]['loss'])

        # Load the best model
        self.model.set_weights(self.model_history[best_epoch]['model'])

    def predict(self, new_sample):
        """Predicts the close price for a new sample."""
        new_sample_scaled = self.scaler_X.transform(
            new_sample).reshape((1, self.time_steps, 11))
        predicted_scaled = self.model.predict(new_sample_scaled)
        predicted_close = self.scaler_y.inverse_transform(predicted_scaled)
        return predicted_close[0, 0]
