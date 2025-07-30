"""
Errors
------

custom exceptions for temds.datasources
"""

class TEMDatasetUninitializedError(Exception):
    """Raised if dataset is None and a base function is called"""
    pass

# class TEMDatasetMissingResolutionError(Exception):
#     """Raised if dataset has unset resolution and the resolution is required to
#     proceed.
#     """
#     pass

# class AnnualDailyContinuityError(Exception):
#     """Raise when if the there is a missing year in..."""
#     pass

# class InvalidCalendarError(Exception):
#     """Raise when the calendar attribute of the time dimension of the dataset is not 365_day or noleap"""
#     pass

# class AnnualDailyYearMismatchError(Exception):
#     """Raise when the year of the file does not match the year of the object"""
#     pass

# class AnnualDailyYearUnknownError(Exception):
#     """Raise when self.year is unkonwn and cannot be loaded."""
#     pass

# class AnnualTimeSeriesError(Exception):
#     """Raise when for errors related to annual time series data."""
#     pass
