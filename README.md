# ptt

~**P**neumatic~ **P**acket **T**ube **T**ransport

Peer-to-peer (p2p), command-line application for secure messaging and file-sharing.

## Overview

`ptt` allows you to securely text and share files with other individuals.

First, specify a peer by public IP address and external port and assign them a memorable, (locally) unique name. Once both peers have added each other's contact information, they can establish a direct, secure communication via TCP hole-punching and TLS session establishment. Then they can send and receive message and files over the connection. All data is encrypted and communicated directly between peers, i.e. there's no intermediary server.

## What's with the name?

**PTT** is an acronym for [pneumatic tube transport](https://en.wikipedia.org/wiki/Pneumatic_tube). This project adopts the acronym and resembles its physical counterpart to a certain degree. A major design goal for `ptt` was seamless p2p connection establishment through firewalls, without sacrificing security. In other words, individuals should be able to quickly assemble and disassemble "tubes" to their peers. They should be able to send/receive content by way of these tubes. Other people who *aren't* peers shouldn't be able to read or write data over the tubes.
