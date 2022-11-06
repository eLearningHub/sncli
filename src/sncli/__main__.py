import sys
import click
from sncli.services.twitter import twitter

@click.group()
def cli():
    pass

cli.add_command(twitter)

if __name__ == '__main__':
    cli()
