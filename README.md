# ptt

~**P**neumatic~ **P**acket **T**ube **T**ransport

Peer-to-peer (p2p), command-line application for secure messaging and file-sharing.

## Overview

`ptt` allows you to securely text and share files with other people.

First, specify a peer by public IP address and external port and assign them a memorable, (locally) unique name. Once both peers have added each other's contact information, they can establish a direct, secure communication via TCP hole-punching and TLS. Then they can send and receive message and files over the connection. All data is encrypted and communicated directly between peers, i.e. there's no intermediary server(s).

## What's with the name?

**PTT** is an acronym for [pneumatic tube transport](https://en.wikipedia.org/wiki/Pneumatic_tube). This project adopts the acronym and resembles its physical counterpart to a certain degree. Think of `ptt` as a tool for assembling, disassembling, and sending/receiving content over digital communication "tubes".
