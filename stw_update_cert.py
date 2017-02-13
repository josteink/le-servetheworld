#!/usr/bin/python3

import argparse
import stw_core
import sys


def main(argv):
    parser = argparse.ArgumentParser(description='Automated certificate update for http://hcp.stwcp.net/')
    parser.add_argument("domain")
    parser.add_argument("certfile")
    parser.add_argument("keyfile")
    args = parser.parse_args(argv)
    stw_core.upload_certificate(args.domain, args.certfile, args.keyfile)


if __name__ == '__main__':
    main(sys.argv[1:])
