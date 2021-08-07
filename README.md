# ptt

~**P**neumatic~ **P**acket **T**ube **T**ransport

Peer-to-peer (p2p), command-line application for secure messaging and file-sharing.

## Overview

`ptt` allows you to securely text and share files directly with people on other home/office networks.

First, specify a peer by public IP address and external port and assign them a memorable, (locally) unique name. Once both peers have added each other's contact information, they can establish a direct, secure communication via TCP hole-punching and TLS. Then they can send and receive message and files over the connection. All data is encrypted and communicated directly between peers, i.e. there's no intermediary server(s).

## What's with the name?

**PTT** is an acronym for [pneumatic tube transport](https://en.wikipedia.org/wiki/Pneumatic_tube). This project adopts the acronym and resembles its physical counterpart to a certain degree. Think of `ptt` as a tool for assembling, disassembling, and sending/receiving content over digital communication "tubes".

## Install

`pip install TBD`

## Usage

### `pttd`

CLI for controlling the daemon, which listens on an IPC socket for `ptt` commands.

**Note:** the daemon *must* be running for `ptt` commands to work!

#### `pttd start [-c, --connect]`

Start the daemon in a separate process.

The `-c` or `--connect` flag instructs the daemon to attempt connecting to each known peer on start-up.

#### `pttd status`

Reports whether daemon is running or not.

#### `pttd stop`

Stop the daemon gracefully.

#### `pttd restart [-c, --connect]`

Restart the daemon. The `-c` or `--connect` flag is the same as in the `start` command.

#### `pttd clean`

Sometimes in development, the daemon gets in a weird state where it doesn't respond to other commands. This command terminates the daemon process and removes any lingering files. A subsequent `pttd start` should successfully start the daemon.

### `ptt`

CLI for performing peer-specific actions.

Each command takes a single argument: the peer's `<alias>`. Other information is prompted when required.

#### `ptt add/add6`

This command adds a new peer to the database, uniquely identified by its `<alias>`.

First, it reserves a local port for peer communication and displays this along with your public IP address. You should share this information with your peer *out-of-band*. Similarly, your peer should share their information with you. You'll be prompted to enter your peer's public IP address and port details.

If you want to use IPv6 addresses, you and your peer should use `add6`.

**Note:** you must use the same IP version as your peer!

#### `ptt show`

Displays the peer's address and port information with connection status.

#### `ptt edit/edit6`

This command changes the peer's alias, local port, remote IP, and/or remote port.

Use `edit6` if you want to assign a public IPv6 address to the peer.

#### `ptt remove`

Remove a peer from the database.

#### `ptt connect`

Establish a direct, secure connection to a peer via TCP hole-punching and TLS. You and your peer should receive desktop notifications upon connecting.

#### `ptt disconnect` *

Disconnect from a peer. Both parties should receive dekstop notifications.

#### `ptt send-text` *

Type and send a text message to a peer. Your peer should receive a desktop notification upon receiving the text.

#### `ptt read-texts`

Show texts sent to/received from a peer, including timstampes when texts were sent/received.

#### `ptt share-file` *

Send a file to a peer. You'll be prompted for the filepath. Your peer should receive a desktop notification upon receiving the file.

#### `ptt list-files`

List names of files that have been sent to/received from the peer, including timestamps when files were shared.

---

\* Must be connected to peer
