"""
Errors
------

custom exceptions for temds.datasources
"""

class UninitializedError(Exception):
    """Raised if dataset is None and a base function is called"""
    pass

# class TEMDatasetMissingResolutionError(Exception):
#     """Raised if dataset has unset resolution and the resolution is required to
#     proceed.
#     """
#     pass

class ContinuityError(Exception):
    """Raise when if the there is a missing year in YearlyTimeseries"""
    pass

# class InvalidCalendarError(Exception):
#     """Raise when the calendar attribute of the time dimension of the dataset is not 365_day or noleap"""
#     pass

# class AnnualDailyYearMismatchError(Exception):
#     """Raise when the year of the file does not match the year of the object"""
#     pass

class YearUnknownError(Exception):
    """Raise when self.year is unkonwn and cannot be loaded."""
    pass

class YearlyTimeSeriesError(Exception):
    """Raise when for errors related to Timeseries """
    pass
