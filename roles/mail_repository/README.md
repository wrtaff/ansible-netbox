# mail_repository
Version: 1.1
Context: http://trac.home.arpa/ticket/3034

## Purpose
This role provisions a centralized Mail Repository and SMTP Relay on a Debian-based host. It is designed to "catch" all internal network traffic and store it in a single IMAP-accessible mailbox.

## Components
* **Postfix:** Configured as a local relay (mynetworks) that aliases all incoming mail to a single system user.
* **Dovecot:** Provides IMAP access and handles local delivery via LMTP.

## Variables
* `mail_repository_catchall_user`: The system user who receives all mail (default: `catchall`).
* `mail_repository_catchall_password`: The password for the catchall user.
* `mail_repository_trusted_networks`: Networks permitted to relay (default: `192.168.0.0/24`).

## Usage
Used by `playbooks/provision_mail_repository.yml`.
