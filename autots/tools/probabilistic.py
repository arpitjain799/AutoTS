"""
Point to Probabilistic
"""
import pandas as pd
import numpy as np
from autots.tools.impute import fake_date_fill
from scipy.stats import percentileofscore
def percentileofscore_appliable(x, a, kind = 'rank'):
    return percentileofscore(a, score = x, kind = kind)

def Variable_Point_to_Probability(train, forecast, alpha = 0.3, beta = 1):
    """Data driven placeholder for model error estimation
    
    Catlin Point to Probability method ('a mixture of dark magic and gum disease')
    
    ErrorRange = beta * (En + alpha * En-1 [cum sum of En])
    En = abs(0.5 - QTP) * D
    D = abs(Xn - ((Avg % Change of Train * Xn-1) + Xn-1))
    Xn = Forecast Value
    QTP = Percentile of Score in All Percent Changes of Train
    Score = Percent Change (from Xn-1 to Xn)
    
    Args:
        train (pandas.DataFrame): DataFrame of time series where index is DatetimeIndex
        forecast (pandas.DataFrame): DataFrame of forecast time series 
            in which the index is a DatetimeIndex and columns/series aligned with train.
            Forecast must be > 1 in length.
        alpha (float): parameter which effects the broadening of error range over time
            Usually 0 < alpha < 1 (although it can be larger than 1)
        beta (float): parameter which effects the general width of the error bar
            Usually 0 < beta < 1 (although it can be larger than 1)
            
    Returns:
        ErrorRange (pandas.DataFrame): error width for each value of forecast.
    """
    column_order = train.columns.intersection(forecast.columns)
    intial_length = len(forecast.columns)
    forecast = forecast[column_order] # align columns
    aligned_length = len(forecast.columns)
    train = train[column_order]
    if aligned_length != intial_length:
        print("Forecast columns do not match train, some series may be lost")
    
    train = train.replace(0, np.nan)
    
    train = fake_date_fill(train, back_method = 'keepNA')
    
    percent_changes = train.pct_change()
    
    median_change = percent_changes.median()
    # median_change = (1  + median_change)
    # median_change[median_change <= 0 ] = 0.01  # HANDLE GOING BELOW ZERO
    
    diffs = abs(forecast - (forecast + forecast * median_change).fillna(method='ffill').shift(1))
    
    forecast_percent_changes = forecast.replace(0, np.nan).pct_change()
    
    quantile_differences = pd.DataFrame()
    for column in forecast.columns:
        percentile_distribution = percent_changes[column].dropna()
        
        quantile_difference = abs((50 - forecast_percent_changes[column].apply(percentileofscore_appliable, a = percentile_distribution, kind = 'rank'))/100)
        quantile_differences = pd.concat([quantile_differences, quantile_difference], axis = 1)
        
    En = quantile_differences * diffs
    Enneg1 = En.cumsum().shift(1).fillna(0)
    ErrorRange = beta * (En + alpha * Enneg1)
    ErrorRange = ErrorRange.fillna(method = 'bfill').fillna(method = 'ffill')
    
    return ErrorRange

def historic_quantile(df_train, prediction_interval: float = 0.9):
    """
    Computes the difference between the median and the prediction interval range in historic data.
    
    Args:
        df_train (pd.DataFrame): a dataframe of training data
        prediction_interval (float): the desired forecast interval range
    
    Returns:
        lower, upper (np.array): two 1D arrays
    """
    quantiles = [0, 1 - prediction_interval, 0.5, prediction_interval, 1]
    bins = np.nanquantile(df_train.astype(float), quantiles, axis=0, keepdims=False)
    upper = bins[3] - bins[2]
    if 0 in upper:
        np.where(upper != 0, upper, (bins[4] - bins[2])/4)
    lower = bins[2] - bins[1]
    if 0 in lower:
        np.where(lower != 0, lower, (bins[2] - bins[0])/4)
    return lower, upper

def Point_to_Probability(train, forecast, prediction_interval = 0.9, method: str = 'variable_pct_change'):
    """Data driven placeholder for model error estimation
    
    Catlin Point to Probability method ('a mixture of dark magic and gum disease')
    
    Does not tune alpha and beta, simply uses defaults!
    
    Args:
        train (pandas.DataFrame): DataFrame of time series where index is DatetimeIndex
        forecast (pandas.DataFrame): DataFrame of forecast time series 
            in which the index is a DatetimeIndex and columns/series aligned with train.
            Forecast must be > 1 in length.
        alpha (float): parameter which effects the broadening of error range over time
            Usually 0 < alpha < 1 (although it can be larger than 1)
        beta (float): parameter which effects the general width of the error bar
            Usually 0 < beta < 1 (although it can be larger than 1)
            
    Returns:
        upper_error, lower_error (two pandas.DataFrames for upper and lower bound respectively)
    """
    if method == 'variable_pct_change':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            beta = np.exp(prediction_interval * 10)
            alpha = 0.3
            errorranges = Variable_Point_to_Probability(train, forecast, alpha = alpha, beta = beta)
            # make symmetric error ranges
            errorranges = errorranges / 2 
            
            upper_forecast = forecast + errorranges
            lower_forecast = forecast - errorranges
            return upper_forecast, lower_forecast
    if method == 'historic_quantile':
        lower, upper = historic_quantile(train, prediction_interval)
        upper_forecast = forecast.astype(float) + upper
        lower_forecast = forecast.astype(float) - lower
        return upper_forecast, lower_forecast
