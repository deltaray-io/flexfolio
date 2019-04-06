|docker build| |docker pulls| |license| 

.. |docker build| image:: https://img.shields.io/docker/cloud/build/xridge/flexfolio.svg
.. |docker pulls| image:: https://img.shields.io/docker/pulls/xridge/flexfolio.svg
.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg

=========
flexfolio
=========

Python Package & Docker image to fetch Flex Statements from Interactive Brokers
and convert it into PyFolio compatible data structures.

Usage
-----
.. code-block:: shell

  $ docker run -v $(pwd)/workdir:/workdir xridge/flexfolio:latest fetch_statement IB_API_KEY QUERY_ID /workdir/flex_report.xml
  2019-04-06 16:23:17,097 - flexfolio.cli - INFO - Requesting statement
  2019-04-06 16:23:17,770 - flexfolio.cli - INFO - Downloading statement
  
  $ docker run -v $(pwd)/workdir:/workdir xridge/flexfolio:latest statement_to_pyfolio --output-format hdf5 /workdir/flex_report.xml /workdir
  2019-04-06 16:24:42,153 - flexfolio.cli - INFO - Storing returns to /workdir/flex_report-returns.hdf5
  2019-04-06 16:24:57,202 - flexfolio.cli - INFO - Storing positions to /workdir/flex_report-positions.hdf5
  2019-04-06 16:24:57,280 - flexfolio.cli - INFO - Storing transactions to /workdir/flex_report-transactions.hdf5

License
-------
`Apache License Version 2.0`_

.. _`Apache License Version 2.0`: http://www.apache.org/licenses/