# -*- coding: utf-8 -*-

"""Console script for flexfolio."""
import sys
import logging
import os.path
from typing import Tuple, Optional, cast
from xml.etree import ElementTree

import click
import polling
import requests

from flexfolio.flex_statement import FlexStatement, ALL_MODELS


FLEX_SERVICE_BASE_URL = \
    'https://gdcdyn.interactivebrokers.com' \
    '/Universal/servlet/FlexStatementService'
FLEX_DL_TIMEOUT = 120

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@click.group()
def main() -> None:
    pass


@main.command()
@click.argument(
    'ib-api-token',
    nargs=1,
    type=click.STRING
)
@click.argument(
    'ib-query-id',
    nargs=1,
    type=click.STRING
)
@click.argument(
    'target-file',
    nargs=1,
    type=click.Path(exists=False, writable=True,
                    file_okay=True, dir_okay=False)
)
def fetch_statement(ib_api_token: str, ib_query_id: str,
                    target_file: str) -> None:
    # Proxy the call via an interim function so that other
    # packages can import this fn and re-use in their cli
    return fetch_statement_logic(ib_api_token, ib_query_id, target_file)


def fetch_statement_logic(ib_api_token: str, ib_query_id: str,
                          target_file: str) -> None:
    def _request_statement() -> Tuple[str, str]:
        url = "{base}.SendRequest?t={token}&q={query_id}&v=3".format(
            base=FLEX_SERVICE_BASE_URL, token=ib_api_token,
            query_id=ib_query_id)

        response = requests.get(url)
        response.raise_for_status()
        tree = ElementTree.fromstring(response.content)

        status = tree.find('./Status')
        if status is None or status.text != 'Success':
            log.error("Error requesting flex report: %s", response.content)
            raise ValueError("Error requesting flex report")

        reference_code = tree.find('./ReferenceCode')
        statement_url = tree.find('./Url')

        assert reference_code is not None
        assert statement_url is not None

        return str(reference_code.text), str(statement_url.text)

    def _download_statement(reference_code: str, statement_url: str) -> bytes:
        url = "{base}?t={token}&q={reference_code}&v=3".format(
            base=statement_url, token=ib_api_token,
            reference_code=reference_code)

        def _download_report() -> Optional[bytes]:
            response = requests.get(url)
            response.raise_for_status()
            tree = ElementTree.fromstring(response.content)

            in_progress = tree.find('./Status')
            if in_progress is None:
                return response.content
            return None

        content = polling.poll(
            _download_report,
            timeout=FLEX_DL_TIMEOUT,
            step=0.1)

        return cast(bytes, content)

    log.info("Requesting statement")
    reference_code, statement_url = _request_statement()

    log.info("Downloading statement")
    flex_stmt = _download_statement(reference_code, statement_url)
    with open(target_file, 'wb') as f:
        f.write(flex_stmt)


@main.command()
@click.argument(
    'flex-statement-path',
    nargs=1,
    type=click.Path(exists=True)
)
@click.argument(
    'target-dir',
    nargs=1,
    type=click.Path(exists=True, writable=True,
                    file_okay=False, dir_okay=True)
)
@click.option(
    '--output-format',
    default='json',
    type=click.Choice(['json', 'hdf5', 'pickle', 'msgpack'])
)
@click.option(
    '--model',
    default=ALL_MODELS
)
def statement_to_pyfolio(flex_statement_path: str,
                         target_dir: str,
                         output_format: str,
                         model: str) -> int:
    report = FlexStatement(flex_statement_path)

    for fn_name in ('returns', 'positions', 'transactions'):
        fn = getattr(report, fn_name)
        df = fn(model)
        file_suffix = \
            os.path.basename(flex_statement_path).replace('.xml', '')
        target_file = \
            '{dir}/{file_base}-{fn}.{format}'.format(
                dir=target_dir,
                file_base=file_suffix,
                fn=fn_name,
                format=output_format)

        log.info("Storing %s to %s", fn_name, target_file)

        if output_format == 'json':
            df.to_json(target_file, orient='table')
        elif output_format == 'hdf5':
            df.to_hdf(target_file, key=fn_name)
        elif output_format == 'pickle':
            df.to_pickle(target_file)
        elif output_format == 'msgpack':
            df.to_msgpack(target_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
