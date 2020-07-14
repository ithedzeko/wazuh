#!/var/ossec/framework/python/bin/python3

# Copyright (C) 2015-2019, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is a free software; you can redistribute it and/or modify it under the terms of GPLv2

import argparse
import ipaddress
import re
import sys
import os
import subprocess

from api.constants import UWSGI_CONFIG_PATH, CONFIG_FILE_PATH, TEMPLATE_API_CONFIG_PATH
from wazuh.core.common import ossec_path
from wazuh import security

_ip_host = re.compile(r'( *)(# )?http:(.*):')
_proxy_value = re.compile(r'(.*)behind_proxy_server:(.*)')
_rbac = re.compile(r'(.*)rbac:(.*)')
_rbac_mode = re.compile(r'(.*)mode: (.*)')
_basic_auth_value = re.compile(r'(.*)basic_auth:(.*)')
_wsgi_socket = re.compile(r'( *)(# )?shared-socket:(.*):')
_wsgi_certs = re.compile(r'https: =.*')

interactive = False


# Check that the uWSGI configuration file exists
def _check_uwsgi_config():
    try:
        with open(UWSGI_CONFIG_PATH, 'r+'):
            return True
    except FileNotFoundError:
        print('[ERROR] uWSGI configuration file does not exists: {}'.format(UWSGI_CONFIG_PATH))

    return False


# Checks that the provided IP is valid
def _check_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        print('[ERROR] Address/Netmask is invalid: {}'.format(ip))
    except Exception as e:
        print('[ERROR] There is a problem with the IP provided: \n{}'.format(e))

    return False


# Checks that the provided port is valid
def _check_port(port):
    if port is not None:
        try:
            if 1 <= int(port) <= 65535:
                return True
        except:
            pass
    print('[ERROR] The port provided is invalid, the port must be a number between 1 and 65535')
    return False


# Checks that the provided component is valid (yes/true, no/false)
def _check_boolean(component, value):
    if value is not None:
        if (value.lower() == 'true' or value.lower() == 'yes') \
                or (value.lower() == 'false' or value.lower() == 'no'):
            return True
        print('[ERROR] Invalid value for {}: {}'.format(component, value))
    return False


# Unify true/false yes/no
def _convert_boolean_to_string(value):
    return 'yes' if value.lower() == 'true' or value.lower() == 'yes' else 'no'


def _open_file():
    try:
        with open(CONFIG_FILE_PATH, 'r+') as f:
            lines = f.readlines()
    except FileNotFoundError:
        with open(TEMPLATE_API_CONFIG_PATH, 'r+') as f:
            lines = f.readlines()

    return lines


def _match_value(regex, lines, value):
    new_file = ''
    for line in lines:
        match = re.search(regex, line)
        if match:
            match_split = line.split(':')
            comment = match_split[0].split('# ')
            if len(comment) > 1:
                match_split[0] = comment[1]
            new_file += match_split[0] + ': ' + value + '\n'
        else:
            new_file += line

    return new_file


# Change the fields that are an IP to the one specified by the user
def change_ip(ip=None):
    while ip != '':
        if interactive:
            ip = input('[INFO] Enter the IP to listen, press enter to not modify: ')
        if ip != '' and _check_ip(ip):
            with open(UWSGI_CONFIG_PATH, 'r+') as f:
                lines = f.readlines()

            new_file = ''
            for line in lines:
                match = re.search(_ip_host, line)
                match_uwsgi = re.search(_wsgi_socket, line)
                if match or match_uwsgi:
                    match_split = line.split(': ')
                    ip_port = match_split[1].split(':')
                    ip_port[0] = ip
                    match_split[1] = ':'.join(ip_port)
                    new_file += ': '.join(match_split)
                else:
                    new_file += line
            if new_file != '':
                with open(UWSGI_CONFIG_PATH, 'w') as f:
                    f.write(new_file)
                print('[INFO] IP changed correctly to \'{}\''.format(ip))

                return True
        elif ip == '' and not interactive:
            print('[INFO] IP not modified')
            return False
    return False


# Change the fields that are a PORT to the one specified by the user
def change_port(port=None):
    while port != '':
        if interactive:
            port = input('[INFO] Enter the PORT to listen, press enter to not modify: ')
        if port != '' and _check_port(port):
            with open(UWSGI_CONFIG_PATH, 'r+') as f:
                lines = f.readlines()

            new_file = ''
            for line in lines:
                match = re.search(_ip_host, line)
                match_uwsgi = re.search(_wsgi_socket, line)
                if match or match_uwsgi:
                    match_split = line.split(':')
                    new_file += match_split[0] + ': ' + match_split[1] + ':' + str(port) + '\n'
                else:
                    new_file += line
            if new_file != '':
                with open(UWSGI_CONFIG_PATH, 'w') as f:
                    f.write(new_file)
                print('[INFO] PORT changed correctly to \'{}\''.format(port))
            return True
        if not interactive:
            return False
    return False


# Enable/Disable/Skip basic authentication
def change_basic_auth(value=None):
    while value is None or value.lower() != 's':
        if interactive:
            value = input('[INFO] Enable user authentication? [Y/n/s]: ')
            if value.lower() == '' or value.lower() == 'y' or value.lower() == 'yes':
                value = 'yes'
                username = input('[INFO] New API user (Press enter to skip, default user is `wazuh`): ')
                if username != '':
                    while True:
                        password = input('[INFO] New password: ')
                        check_pass = input('[INFO] Re-type new password: ')
                        if password == check_pass and password != '':
                            break
                        print('[ERROR] Password verification error: Passwords don\'t match or password is empty.')
                    try:
                        user = security.create_user(username, password)
                        print('[INFO] User created correctly. Username: \'{}\''.format(
                               user['data']['items'][0]['username']))
                    except Exception:
                        print('[ERROR] Username \'{}\' already exist'.format(username))
            elif value.lower() == 'n' or value.lower() == 'no':
                value = 'no'
            else:
                return False

        lines = _open_file()
        value = _convert_boolean_to_string(value)
        new_file = _match_value(_basic_auth_value, lines, value)
        if new_file != '':
            with open(CONFIG_FILE_PATH, 'w') as f:
                f.write(new_file)
                print('[INFO] Basic auth value set to \'{}\''.format(value))
                return True
        if not interactive:
            return False
    return False


# Enable/Disable/Skip behind proxy server
def change_proxy(value=None):
    while value is None or value.lower() != 's':
        if interactive:
            value = input('[INFO] Is the API running behind a proxy server? [y/N/s]: ')
            if value.lower() == 'y' or value.lower() == 'yes':
                value = 'yes'
            elif value.lower() == '' or value.lower() == 'n' or value.lower() == 'no':
                value = 'no'
            else:
                return False
        value = _convert_boolean_to_string(value)
        lines = _open_file()
        new_file = _match_value(_proxy_value, lines, value)
        if new_file != '':
            with open(CONFIG_FILE_PATH, 'w') as f:
                f.write(new_file)
            print('[INFO] PROXY value changed correctly to \'{}\''.format(value))

            return True
        if not interactive:
            return False
    return False


# white/black/White RBAC mode
def change_rbac_mode(value=None):
    while value is None or value.lower() != 'w' or value.lower() != 'b' or value.lower() != '':
        if interactive:
            value = input('[INFO] Choose the mode of RBAC [WHITE-W/black-b]: ')
            if value.lower() == 'w' or value.lower() == 'white' or value.lower() == '':
                value = ' white'
            elif value.lower() == 'b' or value.lower() == 'black':
                value = ' black'
            else:
                print('[ERROR] Invalid RBAC mode: \'{}\''.format(value))
                continue
        lines = _open_file()
        new_file = ''
        for line in lines:
            match = re.search(_rbac, line)
            match_mode = re.search(_rbac_mode, line)
            if match:
                line = line.replace('# ', '')
            elif match_mode:
                split = line.split(':')
                split[0] = split[0].replace('# ', '')
                split[1] = value + '\n'
                line = ':'.join(split)
            new_file += line
        with open(CONFIG_FILE_PATH, 'w') as f:
            f.write(new_file)
        print('[INFO] RBAC mode correctly changed to \'{}\''.format(value))

        return True
    return False


# Enable/Disable HTTP protocol
def change_http(line, value):
    match_split = line.split(':')
    if value == 'yes':
        comment = match_split[0].split('# ')
        if len(comment) > 1:
            match_split[0] = comment[0] + comment[1]
    elif value == 'no' and '# ' not in ''.join(match_split):
        comment = match_split[0].split('h')
        if len(comment) > 1:
            match_split[0] = comment[0] + '# h' + comment[1]

    print('[INFO] HTTP changed correctly to \'{}\''.format(value))
    return ':'.join(match_split)


# Enable/Disable HTTPS protocol
def change_https(value=None, crt_path=None, key_path=None):
    while value is None or value.lower() != 's':
        with open(UWSGI_CONFIG_PATH, 'r+') as f:
            lines = f.readlines()

        if interactive:
            value = input('[INFO] Enable HTTPS and generate SSL certificate? [Y/n/s]: ')
            if value.lower() == '' or value.lower() == 'y' or value.lower() == 'yes':
                value = 'yes'
                crt_path = str(input('[INFO] Introduce the absolute path of your certificate: '))
                key_path = str(input('[INFO] Introduce the absolute path of your key: '))
            elif value.lower() == 'n' or value.lower() == 'no':
                value = 'no'
            else:
                return False

        if crt_path and key_path and (not os.path.isfile(crt_path) or not os.path.isfile(key_path)):
            print('[ERROR] Invalid path for the certificate and the key, please check that both files exist. '
                  'Exiting...')
            return
        value = _convert_boolean_to_string(value)
        new_file = ''
        for line in lines:
            match = re.search(_wsgi_socket, line)
            match_cert = re.search(_wsgi_certs, line)
            match_http = re.search(_ip_host, line)
            if match_http:
                if value == 'yes':
                    line = change_http(line, 'no')
                else:
                    line = change_http(line, 'yes')
                new_file += line
            elif match or match_cert:
                match_split = line.split(':')
                if value == 'yes':
                    comment = match_split[0].split('# ')
                    if len(comment) > 1:
                        match_split[0] = comment[0] + comment[1]
                    if match_cert:
                        splitted = match_split[1].split(',')
                        splitted[1] = crt_path
                        splitted[2] = key_path
                        match_split[1] = ','.join(splitted)
                elif '# ' not in ''.join(match_split):  # If it is not already disable
                    if match:
                        # Split by shared-socket (sh)
                        comment = match_split[0].split('sh')
                        if len(comment) > 1:
                            match_split[0] = comment[0] + '# sh' + comment[1]
                    elif match_cert:
                        comment = match_split[0].split('h')
                        if len(comment) > 1:
                            match_split[0] = comment[0] + '# h' + comment[1]
                new_file += ':'.join(match_split)
            else:
                new_file += line
        if new_file != '':
            with open(UWSGI_CONFIG_PATH, 'w') as f:
                f.write(new_file)
            print('[INFO] HTTPS changed correctly to \'{}\''.format(value))
            return True
        if not interactive:
            return False
    return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help="Change port number", type=int)
    parser.add_argument('-i', '--ip', help="Change the host IP", type=str)
    parser.add_argument('-b', '--basic', help="Configure basic authentication (true/false)", type=str)
    parser.add_argument('-x', '--proxy', help="Yes to run API behind a proxy", type=str)
    parser.add_argument('-r', '--rbac', help="Change the RBAC mode (white/black)", type=str)
    parser.add_argument('-t', '--http', help="Enable http protocol (true/false)", type=str)
    parser.add_argument('-s', '--https', help="Enable https protocol (true/false)", type=str)
    parser.add_argument('-sC', '--sCertificate', help="Set the ssl certificate (path)", type=str)
    parser.add_argument('-sK', '--sKey', help="Set the ssl key (path)", type=str)
    parser.add_argument('-R', '--restart', help="Restart Wazuh after modifications", action='store_true')
    parser.add_argument('-I', '--interactive', help="Enables guided configuration", action='store_true')
    args = parser.parse_args()

    if _check_uwsgi_config() and len(sys.argv) > 1 and not args.interactive:
        if args.ip:
            change_ip(args.ip)
        if args.port:
            change_port(args.port)
        if _check_boolean('proxy', args.proxy):
            change_proxy(args.proxy)
        if _check_boolean('basic auth', args.basic):
            change_basic_auth(args.basic)
        if _check_boolean('https', args.https):
            if not args.sCertificate or not args.sKey:
                print('[ERROR] HTTPS option must be accompanied with \'-sC\' and \'-sK\' options')
            else:
                change_https(args.https, args.sCertificate, args.sKey)
        if args.rbac:
            change_rbac_mode(args.rbac)
        if _check_boolean('http', args.http):
            if args.http.lower() == 'true' or args.http.lower() == 'yes':
                args.http = 'yes'
            elif args.http.lower() == 'false' or args.http.lower() == 'no':
                args.http = 'no'
            change_https(args.http)
        if args.restart:
            print('[INFO] Restarting Wazuh...')
            subprocess.call(ossec_path + '/bin/ossec-control restart', shell=True)
    elif args.interactive or len(sys.argv) == 1:
        interactive = True
        print('[INFO] Interactive mode!')
        change_ip()
        change_port()
        change_proxy()
        change_basic_auth()
        change_rbac_mode()
        change_https()
        print('[INFO] Restarting Wazuh...')
        subprocess.call(ossec_path + '/bin/ossec-control restart', shell=True)
    else:
        print('[ERROR] Please check that your configuration is correct')
