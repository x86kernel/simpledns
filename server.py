from __future__ import print_function

import argparse
import socket
import struct

make8bits = (lambda x : (8 - len(x)) * '0' + x)
isLDH = (lambda x : x if (x.isalpha() or x.isdigit() or x == '-') else '.')

class DNSQuery:
    def __init__(self, packet):
        self.data = packet

        tid_raw = self.data[:2]
        self.tid = struct.unpack('>H', tid_raw)[0]

        self.flags = make8bits(bin(ord(self.data[2])).replace('0b', ''))
        self.flags += make8bits(bin(ord(self.data[3])).replace('0b', ''))

        self.QR = int(self.flags[0])
        self.Opcode = self.flags[1 : 6]

        self.QDCount = 0
        if not self.QR:
            self.QDCount = struct.unpack('>H', self.data[4 : 6])[0]

            if self.QDCount:
                self.raw_queries = self.data[13:]
                for byte in self.raw_queries:
                    if ord(byte) == 0x00:
                        endindex = self.raw_queries.index(byte) + 1
                        self.query_Name = self.raw_queries[: endindex]
                        self.query_Type = self.raw_queries[endindex : endindex + 2]
                        self.query_Class = self.raw_queries[endindex + 2 : endindex + 4]

                        break
                self.query_Name = ''.join(map(isLDH, self.query_Name))
                self.query_Type = struct.unpack('>H', self.query_Type)[0]
                self.query_Class = struct.unpack('>H', self.query_Class)[0]

    def MakeResponse(self, dnsmap):
        if self.QR:
            return ''

        namelen = len(self.query_Name)
        isinmap = dnsmap.has_key(self.query_name[: namelen - 1])

        response_packet = struct.pack('>H', self.tid)

        response_flags = list(self.flags)
        if not isinmap or self.query_Type == 28: # query_Type = 1 -> ipv6.. 
            #Set error bits
            response_flags[14] = '1' 
            response_flags[15] = '1'

        response_flags[0] = '1'
        response_flags = ''.join(response_flags)

        response_packet += struct.pack('>H', int(response_flags, 2))

        response_packet += struct.pack('>H', 1)
        response_packet += struct.pack('>H', 1)
        response_packet += struct.pack('>H', 0)
        response_packet += struct.pack('>H', 0)

        name = self.query_Name.split('.')
        name = map(lambda x : list(x), name)
        map(lambda x : x.insert(0, chr(len(x))), name)

        name = ''.join(map(lambda x : ''.join(x), name))

        response_packet += name
        response_packet += struct.pack('>H', 1)
        response_packet += struct.pack('>H', self.query_Class)

        response_packet += "\xc0\x0c"
        response_packet += struct.pack('>H', 1)
        response_packet += struct.pack('>H', self.query_Class)
        response_packet += struct.pack('>I', 60)

        if isinmap:
            response_packet += struct.pack('>H', 4)

            ipaddr = dnsmap[self.query_Name[: namelen - 1]]
            response_packet += ''.join(map(lambda x : chr(int(x)), ipaddr.split('.')))

        return response_packet

    def GetRequestName(self):
        return self.query_Name

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dnsmap', help = "dns map file")
    args = parser.parse_args()

    if not args.dnsmap:
        exit(0)

    try:
        f = open(args.dnsmap, 'r')
    except IOError:
        print ('cannot open file', args.dnsmap)
        exit(0)

    dnsmap = dict(map(lambda x : x.split(), f.readlines()))

    udps_dsc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udps_dsc.bind(('', 53))

    try:
        while 1:
            data, addr = udps_dsc.recvfrom(1024)
            dnspacket = DNSQuery(data)

            requestname = dnspacket.GetRequestName()
            requestlen = len(requestname)

            if dnsmap.has_key(requestname[: requestlen - 1]):
                print (requestname, ' Request from [', addr[0], '] ->', 'Response: [', dnsmap[requestname[: requestlen - 1]], ']')
            else:
                print (requestname, ' Request from [', addr[0], '] ->', 'Response: Non-existent domain')

                udps_dsc.sendto(dnspacket.MakeResponse(dnsmap), addr)
    except KeyboardInterrupt:
        udps_dsc.close()
        exit(0)
