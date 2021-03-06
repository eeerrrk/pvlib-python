import logging
pvl_logger = logging.getLogger('pvlib')

import numpy as np
import pandas as pd

from nose.tools import raises, assert_almost_equals
from numpy.testing import assert_almost_equal

from pandas.util.testing import assert_frame_equal

from pvlib.location import Location
from pvlib import clearsky
from pvlib import solarposition
from pvlib import irradiance
from pvlib import atmosphere

from . import requires_ephem

# setup times and location to be tested.
tus = Location(32.2, -111, 'US/Arizona', 700)

# must include night values
times = pd.date_range(start='20140624', end='20140626', freq='1Min',
                      tz=tus.tz)

ephem_data = solarposition.get_solarposition(
    times, tus.latitude, tus.longitude, method='nrel_numpy')

irrad_data = clearsky.ineichen(times, tus.latitude, tus.longitude,
                               altitude=tus.altitude, linke_turbidity=3,
                               solarposition_method='nrel_numpy')

dni_et = irradiance.extraradiation(times.dayofyear)

ghi = irrad_data['ghi']


# the test functions. these are almost all functional tests.
# need to add physical tests.

def test_extraradiation():
    assert_almost_equals(1382, irradiance.extraradiation(300), -1)


def test_extraradiation_dtindex():
    irradiance.extraradiation(times)


def test_extraradiation_doyarray():
    irradiance.extraradiation(times.dayofyear)


def test_extraradiation_asce():
    assert_almost_equals(
        1382, irradiance.extraradiation(300, method='asce'), -1)


def test_extraradiation_spencer():
    assert_almost_equals(
        1382, irradiance.extraradiation(300, method='spencer'), -1)


@requires_ephem
def test_extraradiation_ephem_dtindex():
    irradiance.extraradiation(times, method='pyephem')


@requires_ephem
def test_extraradiation_ephem_scalar():
    assert_almost_equals(
        1382, irradiance.extraradiation(300, method='pyephem').values[0], -1)


@requires_ephem
def test_extraradiation_ephem_doyarray():
    irradiance.extraradiation(times.dayofyear, method='pyephem')


def test_grounddiffuse_simple_float():
    irradiance.grounddiffuse(40, 900)


def test_grounddiffuse_simple_series():
    ground_irrad = irradiance.grounddiffuse(40, ghi)
    assert ground_irrad.name == 'diffuse_ground'


def test_grounddiffuse_albedo_0():
    ground_irrad = irradiance.grounddiffuse(40, ghi, albedo=0)
    assert 0 == ground_irrad.all()


@raises(KeyError)
def test_grounddiffuse_albedo_invalid_surface():
    irradiance.grounddiffuse(40, ghi, surface_type='invalid')


def test_grounddiffuse_albedo_surface():
    irradiance.grounddiffuse(40, ghi, surface_type='sand')


def test_isotropic_float():
    irradiance.isotropic(40, 100)


def test_isotropic_series():
    irradiance.isotropic(40, irrad_data['dhi'])


def test_klucher_series_float():
    irradiance.klucher(40, 180, 100, 900, 20, 180)


def test_klucher_series():
    irradiance.klucher(40, 180, irrad_data['dhi'], irrad_data['ghi'],
                       ephem_data['apparent_zenith'],
                       ephem_data['azimuth'])


def test_haydavies():
    irradiance.haydavies(40, 180, irrad_data['dhi'], irrad_data['dni'],
                         dni_et,
                         ephem_data['apparent_zenith'],
                         ephem_data['azimuth'])


def test_reindl():
    irradiance.reindl(40, 180, irrad_data['dhi'], irrad_data['dni'],
                      irrad_data['ghi'], dni_et,
                      ephem_data['apparent_zenith'],
                      ephem_data['azimuth'])


def test_king():
    irradiance.king(40, irrad_data['dhi'], irrad_data['ghi'],
                    ephem_data['apparent_zenith'])


def test_perez():
    am = atmosphere.relativeairmass(ephem_data['apparent_zenith'])
    out = irradiance.perez(40, 180, irrad_data['dhi'], irrad_data['dni'],
                     dni_et, ephem_data['apparent_zenith'],
                     ephem_data['azimuth'], am)
    assert not out.isnull().any()

# klutcher (misspelling) will be removed in 0.3
def test_total_irrad():
    models = ['isotropic', 'klutcher', 'klucher',
              'haydavies', 'reindl', 'king', 'perez']
    AM = atmosphere.relativeairmass(ephem_data['apparent_zenith'])

    for model in models:
        total = irradiance.total_irrad(
            32, 180,
            ephem_data['apparent_zenith'], ephem_data['azimuth'],
            dni=irrad_data['dni'], ghi=irrad_data['ghi'],
            dhi=irrad_data['dhi'],
            dni_extra=dni_et, airmass=AM,
            model=model,
            surface_type='urban')

        assert total.columns.tolist() == ['poa_global', 'poa_direct',
                                          'poa_diffuse', 'poa_sky_diffuse',
                                          'poa_ground_diffuse']


def test_globalinplane():
    aoi = irradiance.aoi(40, 180, ephem_data['apparent_zenith'],
                         ephem_data['azimuth'])
    airmass = atmosphere.relativeairmass(ephem_data['apparent_zenith'])
    gr_sand = irradiance.grounddiffuse(40, ghi, surface_type='sand')
    diff_perez = irradiance.perez(
        40, 180, irrad_data['dhi'], irrad_data['dni'], dni_et,
        ephem_data['apparent_zenith'], ephem_data['azimuth'], airmass)
    irradiance.globalinplane(
        aoi=aoi, dni=irrad_data['dni'], poa_sky_diffuse=diff_perez,
        poa_ground_diffuse=gr_sand)


def test_disc_keys():
    clearsky_data = clearsky.ineichen(times, tus.latitude, tus.longitude,
                                      linke_turbidity=3)
    disc_data = irradiance.disc(clearsky_data['ghi'], ephem_data['zenith'],
                                ephem_data.index)
    assert 'dni' in disc_data.columns
    assert 'kt' in disc_data.columns
    assert 'airmass' in disc_data.columns


def test_disc_value():
    times = pd.DatetimeIndex(['2014-06-24T12-0700','2014-06-24T18-0700'])
    ghi = pd.Series([1038.62, 254.53], index=times)
    zenith = pd.Series([10.567, 72.469], index=times)
    pressure = 93193.
    disc_data = irradiance.disc(ghi, zenith, times, pressure=pressure)
    assert_almost_equal(disc_data['dni'].values,
                        np.array([830.46, 676.09]), 1)


def test_dirint():
    clearsky_data = clearsky.ineichen(times, tus.latitude, tus.longitude,
                                      linke_turbidity=3)
    pressure = 93193.
    dirint_data = irradiance.dirint(clearsky_data['ghi'], ephem_data['zenith'],
                                    ephem_data.index, pressure=pressure)

def test_dirint_value():
    times = pd.DatetimeIndex(['2014-06-24T12-0700','2014-06-24T18-0700'])
    ghi = pd.Series([1038.62, 254.53], index=times)
    zenith = pd.Series([10.567, 72.469], index=times)
    pressure = 93193.
    dirint_data = irradiance.dirint(ghi, zenith, times, pressure=pressure)
    assert_almost_equal(dirint_data.values,
                        np.array([928.85, 688.26]), 1)


def test_dirint_nans():
    times = pd.DatetimeIndex(start='2014-06-24T12-0700', periods=5, freq='6H')
    ghi = pd.Series([np.nan, 1038.62, 1038.62, 1038.62, 1038.62], index=times)
    zenith = pd.Series([10.567, np.nan, 10.567, 10.567, 10.567,], index=times)
    pressure = pd.Series([93193., 93193., np.nan, 93193., 93193.], index=times)
    temp_dew = pd.Series([10, 10, 10, np.nan, 10], index=times)
    dirint_data = irradiance.dirint(ghi, zenith, times, pressure=pressure,
                                    temp_dew=temp_dew)
    assert_almost_equal(dirint_data.values,
                        np.array([np.nan, np.nan, np.nan, np.nan, 934.2]), 1)


def test_dirint_tdew():
    times = pd.DatetimeIndex(['2014-06-24T12-0700','2014-06-24T18-0700'])
    ghi = pd.Series([1038.62, 254.53], index=times)
    zenith = pd.Series([10.567, 72.469], index=times)
    pressure = 93193.
    dirint_data = irradiance.dirint(ghi, zenith, times, pressure=pressure,
                                    temp_dew=10)
    assert_almost_equal(dirint_data.values,
                        np.array([934.06, 640.67]), 1)

def test_dirint_no_delta_kt():
    times = pd.DatetimeIndex(['2014-06-24T12-0700','2014-06-24T18-0700'])
    ghi = pd.Series([1038.62, 254.53], index=times)
    zenith = pd.Series([10.567, 72.469], index=times)
    pressure = 93193.
    dirint_data = irradiance.dirint(ghi, zenith, times, pressure=pressure,
                                    use_delta_kt_prime=False)
    assert_almost_equal(dirint_data.values,
                        np.array([901.56, 674.87]), 1)

def test_dirint_coeffs():
    coeffs = irradiance._get_dirint_coeffs()
    assert coeffs[0,0,0,0] == 0.385230
    assert coeffs[0,1,2,1] == 0.229970
    assert coeffs[3,2,6,3] == 1.032260


def test_erbs():
    ghi = pd.Series([0, 50, 1000, 1000])
    zenith = pd.Series([120, 85, 10, 10])
    doy = pd.Series([1, 1, 1, 180])
    expected = pd.DataFrame(np.
        array([[ -0.00000000e+00,   0.00000000e+00,  -0.00000000e+00],
               [  9.67127061e+01,   4.15709323e+01,   4.05715990e-01],
               [  7.94187742e+02,   2.17877755e+02,   7.18119416e-01],
               [  8.42358014e+02,   1.70439297e+02,   7.68919470e-01]]),
        columns=['dni', 'dhi', 'kt'])

    out = irradiance.erbs(ghi, zenith, doy)

    assert_frame_equal(out, expected)


def test_erbs_all_scalar():
    ghi = 1000
    zenith = 10
    doy = 180
    expected = pd.DataFrame(np.
        array([[  8.42358014e+02,   1.70439297e+02,   7.68919470e-01]]),
        columns=['dni', 'dhi', 'kt'])

    out = irradiance.erbs(ghi, zenith, doy)

    assert_frame_equal(out, expected)
