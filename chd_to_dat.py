import sys
import os
import struct
import json
import zlib
import lzma
import math

#filename = "Link - The Faces of Evil (Europe).chd"
#filename = "Zelda - The Wand of Gamelon (USA).chd"

# Subcode seems to be stripped from the CD-I files I have access to.
IGNORE_SUBCODE = True

# --- classes ---


class BitStream:
    def __init__(self, byteArray, cursor=0):
        assert cursor >= 0
        self.bytes = byteArray
        self.cursor = 0
        self._byteCursor = 0
        self._accumulator = 0
        self._bitsInAccumulator = 0

        if cursor != 0:
            self.seek(cursor)

    def __len__(self):
        return len(self.bytes) * 8

    def __repr__(self):
        return "BitStream(" + repr(self.bytes) + ", cursor = " + str(self.cursor) + ")"

    def seek(self, offset):
        assert offset >= 0
        assert offset < len(self)

        self._byteCursor = offset // 8
        offsetBits = offset % 8
        self._accumulator = 0
        self._bitsInAccumulator = 0

        self.cursor = offset - offsetBits
        self.remove(offsetBits)

    def _fetch(self, count):
        while self._bitsInAccumulator < count:
            if self._byteCursor < len(self.bytes):
                self._accumulator |= self.bytes[self._byteCursor] << (24 - self._bitsInAccumulator)
            self._byteCursor += 1
            self._bitsInAccumulator += 8

    def peek(self, count):
        assert count >= 0
        assert count <= 24
        if count == 0:
            return 0

        self._fetch(count)

        return self._accumulator >> (32 - count)

    def remove(self, count):
        assert count >= 0
        if count == 0:
            return
        assert count <= 24

        self._fetch(count)
        self._removeWithoutFetch(count)

    def _removeWithoutFetch(self, count):
        assert count <= self._bitsInAccumulator
        self._accumulator = (self._accumulator << count) & 0xFFFF_FFFF
        self._bitsInAccumulator -= count
        self.cursor += count

    def read(self, count):
        assert count >= 0
        assert count <= 24

        ret = self.peek(count)
        self._removeWithoutFetch(count)

        return ret


test = BitStream(b'12345', cursor=1)
value = test.peek(24)
expectedValue = ((b'1'[0] << 16) + (b'2'[0] << 8) + b'3'[0]) << 1
assert value == expectedValue, value

test = BitStream(bytearray([0x21, 0x56, 0x68, 0x83, 0x68, 0x88, 0x88, 0x86]))
value = test.read(4)
assert value == 2, value
value = test.read(4)
assert value == 1, value
value = test.read(4)
assert value == 5, value

del test
del value
del expectedValue

print("All tests passed")


# Based heavily on https://github.com/mamedev/mame/blob/ee1e4f9683a4953cb9d88f9256017fcbc38e3144/src/lib/util/huffman.cpp
class HuffmanCodedData:
    def __init__(self, bitbuf):
        self.maxbits = 8
        self.numcodes = 16

        self.huffnodes = [HuffmanCodedDataNode(i) for i in range(self.numcodes)]
        self.lookup = [None] * (1 << self.maxbits)

        self._readTree(bitbuf)


    def _readTree(self, bitbuf):
        numbits = 4

        curnode = 0
        while curnode < self.numcodes:
            nodebits = bitbuf.read(numbits)
            if nodebits != 1:
                self.huffnodes[curnode].numbits = nodebits
                curnode += 1
            else:
                nodebits = bitbuf.read(numbits)
                if nodebits == 1:
                    self.huffnodes[curnode].numbits = 1
                    curnode += 1
                else:
                    repcount = bitbuf.read(numbits) + 3
                    for i in range(repcount):
                        self.huffnodes[curnode + i].numbits = nodebits
                    curnode += repcount
        assert curnode == self.numcodes

        self._assignCanonicalCodes()
        self._buildLookupTable()

    def _assignCanonicalCodes(self):
        histogram = [0] * 33
        for node in self.huffnodes:
            histogram[node.numbits] += 1

        codeStartNumbers = [0] * 33
        currentStart = 0
        for i in range(32, 0, -1):
            nextStart = (currentStart + histogram[i]) >> 1
            codeStartNumbers[i] = currentStart
            currentStart = nextStart

        for node in self.huffnodes:
            node.bits = codeStartNumbers[node.numbits]
            codeStartNumbers[node.numbits] += 1

    def _buildLookupTable(self):
        for node in self.huffnodes:
            if node.numbits > 0:
                shift = self.maxbits - node.numbits
                for i in range(node.bits << shift, (node.bits + 1) << shift):
                    self.lookup[i] = node

    def readOne(self, bitbuf):
        node = self.lookup[bitbuf.peek(self.maxbits)]
        bitbuf.remove(node.numbits)
        return node.value


class HuffmanCodedDataNode:
    def __init__(self, value, numbits = 0, bits = 0):
        self.numbits = numbits
        self.bits = bits
        self.value = value

    def codedValue(self):
        return ("{:0" + str(self.numbits) + "b}").format(self.bits)

    def __repr__(self):
        return "HuffmanCodedDataNode({:04b}, numbits = {}, bits = {:b}, codedValue = {})" \
            .format(self.value, self.numbits, self.bits, self.codedValue())

test = HuffmanCodedData(BitStream(bytearray([0x21, 0x15, 0x66, 0x88, 0x36, 0x18, 0x36])))
assert [(n.numbits, n.bits) for n in test.huffnodes] == [
    (2, 1),
    (1, 1),
    (5, 3),
    (6, 2),
    (6, 3),
    (8, 0),
    (8, 1),
    (3, 1),
    (6, 4),
    (8, 2),
    (8, 3),
    (8, 4),
    (8, 5),
    (8, 6),
    (8, 7),
    (6, 5)
], print(str(test.huffnodes).replace("),", "),\n"))

assert None not in test.lookup
del test
print("All tests passed")


# Misc CD format info
# From https://github.com/mamedev/mame/blob/f1f77b1a1c4d99d78d0715a1e36ec9ab8e2c8f7d/src/lib/util/cdrom.h#L28
CDRomConstants = {
    # Tracks are padded to this many frames
    "TRACK_PADDING": 4,
    "MAX_SECTOR_DATA": 2352,
    "MAX_SUBCODE_DATA": 96,
    # CHD_FRAME should not be confused with CD frames!
    "CHD_FRAME_SIZE": 2352 + 96,
    "ECC_OFFSET": 0x81C,
    "ECC_LENGTH": 86 * 2 + 52 * 2
}

CD_SYNC_HEADER = bytes([
    0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00
])
CD_SYNC_HEADER





class ChdHunkMap:
    def __init__(self, data, hunkCount):
        mapDataLen = struct.unpack(">I", data[:4])[0]
        self.dataStartOffset = struct.unpack(">Q", b'\0\0' + data[4:10])[0]
        self.crc, self.lengthBits, self.hunkRefBits, self.parentRefBits = \
            struct.unpack(">H3B", data[10:15])
        bitBuffer = BitStream(data[16:mapDataLen])
        compressedData = HuffmanCodedData(bitBuffer)

        compressionTypeArray = []
        prevType = 0 # Arrays CAN start with a run length entry "repeating" this type before the first entry is added
                     # to the array!!
        while len(compressionTypeArray) < hunkCount:
            compressionType = compressedData.readOne(bitBuffer)
            if compressionType == 7:
                count = 3 + compressedData.readOne(bitBuffer)
                for _ in range(count):
                    compressionTypeArray.append(prevType)
            elif compressionType == 8:
                highPart = compressedData.readOne(bitBuffer)
                lowPart = compressedData.readOne(bitBuffer)
                count = 19 + (highPart << 4) + lowPart
                for _ in range(count):
                    compressionTypeArray.append(prevType)
            else:
                assert compressionType < 7, str(compressionType)
                compressionTypeArray.append(compressionType)
                prevType = compressionType

        assert len(compressionTypeArray) == hunkCount

        self.hunks = []
        currentOffset = self.dataStartOffset
        for compressor in compressionTypeArray:
            hunk = ChdHunk(compressor, currentOffset)
            if compressor < 4:
                hunk.compressedLength = bitBuffer.read(self.lengthBits)
                currentOffset += hunk.compressedLength
                hunk.crc = bitBuffer.read(16)
            else:
                raise Exception("Not implemented")
            self.hunks.append(hunk)

        print("Hunk end offset:", self.hunks[-1].offset)
        print("hunk count", len(self.hunks))

    def toDict(self):
        return {
            "crc": self.crc,
            "dataStartOffset": self.dataStartOffset,
            "lengthBits": self.lengthBits,
            "hunkRefBits": self.hunkRefBits,
            "parentRefBits": self.parentRefBits,
            "hunks": [h.toDict() for h in self.hunks]
        }


# Hunks are multiple sectors appended to each other.
class ChdHunk:
    def __init__(self, compressor, offset):
        self.compressorId = compressor
        self.compressorName = None
        self.compressedData = None
        self.data = None
        self.offset = offset
        self.compressedLength = None
        self.crc = None
        self.sectors = None

    def _dictSizeFromHunkLen(self, hunkLength):
        # Find the smallest power of 2 greater than or equal to 2^11 that can fit hunkLength
        for i in range(11, 32):
            if hunkLength < (1 << i):
                return 1 << i
        raise Exception()

    # Based on https://github.com/mamedev/mame/blob/master/src/lib/util/chdcodec.cpp#L382
    def decompress(self, data, hunkLength):
        self.compressedData = data
        assert hunkLength % CDRomConstants["CHD_FRAME_SIZE"] == 0

        # Compute header size
        chdFrames = hunkLength // CDRomConstants["CHD_FRAME_SIZE"]
        if hunkLength < 65536:
            complenBytes = 2
        else:
            complenBytes = 3
        eccBytes = (chdFrames + 7) // 8
        headerBytes = eccBytes + complenBytes


        # "Extract compressed length of base"... unsure what that means?
        try:
            complenBase = (data[eccBytes] << 8) + data[eccBytes + 1]
            if complenBytes > 2:
                complenBase = (complenBase << 8) + data[eccBytes + 2]
        except IndexError as e:
            #raise Exception("Hunk with offset {} doesn't have enough bytes; need at least {} bytes, but has {}." \
            #               .format(self.offset, headerBytes, len(data)))
            return

        assert headerBytes + complenBase <= len(data)
        baseData = data[headerBytes:headerBytes + complenBase]
        subcodeData = data[headerBytes + complenBase:]

        expectedLen = chdFrames * CDRomConstants["MAX_SECTOR_DATA"]
        if self.compressorName == 'cdzl':
            inflatedBaseData = zlib.decompress(baseData, wbits=-15)

            if len(inflatedBaseData) != expectedLen:
                print("Expected base data size", expectedLen, "found", len(inflatedBaseData), \
                      "with compressor", self.compressorName)

        elif self.compressorName == 'cdlz':
            decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[
                {"id": lzma.FILTER_LZMA1, "preset": 9, "dict_size": self._dictSizeFromHunkLen(hunkLength)}
            ])
            inflatedBaseData = decompressor.decompress(baseData, max_length = hunkLength)
            if len(decompressor.unused_data) > 0:
                print("needs_input:", decompressor.needs_input, "unused length:", len(decompressor.unused_data))

            if len(inflatedBaseData) > expectedLen:
                excessData = inflatedBaseData[expectedLen:]
                if len(list(filter(lambda b: b != 0, excessData))):
                    print("Expected base data size", expectedLen, "found", len(inflatedBaseData), \
                      "with compressor", self.compressorName)
                    print("\tExtra data:", excessData)

            while len(inflatedBaseData) < expectedLen:
                inflatedBaseData += b'\0'
        else:
            raise Exception("Not implemented: " + self.compressorName)

        if not IGNORE_SUBCODE:
            inflatedSubcodeData = zlib.decompress(subcodeData, wbits=-15)
            expectedLen = chdFrames * CDRomConstants["MAX_SUBCODE_DATA"]
            if len(inflatedSubcodeData) != expectedLen:
                print("Expected subcode data size", expectedLen, "found", len(inflatedSubcodeData))


        self.sectors = []
        eccBitvec = data[:eccBytes]
        for frameNumber in range(chdFrames):
            sectorStart = frameNumber * CDRomConstants["MAX_SECTOR_DATA"]
            subcodeStart = frameNumber * CDRomConstants["MAX_SUBCODE_DATA"]

            sectorData = inflatedBaseData[sectorStart:sectorStart + CDRomConstants["MAX_SECTOR_DATA"]]
            if not IGNORE_SUBCODE:
                subcodeData = inflatedSubcodeData[subcodeStart:subcodeStart + CDRomConstants["MAX_SUBCODE_DATA"]]

            # Error correcting code related stuff. CD Rom data structure will handle this.
            hasEcc = eccBitvec[frameNumber // 8] & (1 << (frameNumber % 8)) != 0

            self.sectors.append({
                "sector": sectorData,
                "hasEcc": hasEcc
            })
            if not IGNORE_SUBCODE:
                self.sectors[-1]["subcode"] = subcodeData


    def toDict(self):
        return {
            #"compressorId": self.compressorId,
            "compressorName": self.compressorName,
            "offset": self.offset,
            "sectors": self.sectors,
            "crc": self.crc
        }


class ChdMetadataEntry:
    def __init__(self, tag, flagByte, dataString):
        self.tag = tag
        self.flagByte = int(flagByte)
        self.dataString = dataString

        if tag == "CHT2":
            self.data = {}
            for kvpair in dataString.split():
                [key, value] = kvpair.split(':')
                self.data[key] = value
        else:
            self.data = None

    def to_dict(self):
        return {
            "tag": self.tag,
            "flagByte": self.flagByte,
            "dataString": self.dataString,
            "data": self.data
        }

class ChdFile:
    def __init__(self, data):
        # Main Header
        assert data[:8] == b'MComprHD'
        headerLen, versionNumber = struct.unpack(">II", data[8:16])
        assert versionNumber == 5
        assert headerLen == 124

        self.compressorCodecs = list(map(lambda b: b.decode('ascii'), filter(lambda b: b[0] != 0, \
                                            struct.unpack(">4s4s4s4s", data[16:32]))))
        self.uncompressedSize, mapOffset, metaOffset, self.hunkSize, self.unitSize = \
            struct.unpack(">QQQII", data[32:64])
        self.hunkCount = (self.uncompressedSize + self.hunkSize - 1) // self.hunkSize
        self.unitCount = (self.uncompressedSize + self.unitSize - 1) // self.unitSize
        self.rawSha1 = data[64:84]
        self.fullSha1 = data[84:104]
        self.parentSha1 = data[104:124]

        # Hunk Map
        print(hex(mapOffset))
        mapData = data[mapOffset:]
        self.map = ChdHunkMap(mapData, self.hunkCount)
        for hunk in self.map.hunks:
            if hunk.compressorId < 4:
                hunk.compressorName = self.compressorCodecs[hunk.compressorId]
            hunk.decompress(data[hunk.offset:hunk.offset + hunk.compressedLength], self.hunkSize)

        # Metadata
        self.metadata = []
        nextOffset = metaOffset
        while nextOffset != 0:
            rawTag, flags, lengthBytes, nextOffset = \
                struct.unpack(">4sB3sQ", data[metaOffset:metaOffset + 16])
            length = struct.unpack(">I", b'\0' + lengthBytes)[0]
            rawMetadataString = data[metaOffset + 16:metaOffset + 16 + length]
            metadataString = rawMetadataString.split(b'\0')[0].decode('ascii')
            tag = rawTag.split(b'\0')[0].decode('ascii')
            self.metadata.append(ChdMetadataEntry(tag, flags, metadataString))

    def toDict(self):
        return {
            "compressorCodecs": self.compressorCodecs,
            "uncompressedSize": self.uncompressedSize,
            "hunkSize": self.hunkSize,
            "unitSize": self.unitSize,
            "rawSha1": self.rawSha1,
            "fullSha1": self.fullSha1,
            "parentSha1": self.parentSha1,
            "map": self.map.toDict(),
            "metadata": list(map(lambda m: m.to_dict(), self.metadata))
        }


def fromBcd(n):
    return (n // 16 * 10) + (n % 16)


class CDImage:
    def __init__(self, chdFile):
        self.allSectors = []

        # The first two seconds of sectors (ToC) are not present in chd format.
        index = 75 * 2
        for hunk in chdFile.map.hunks:
            if hunk.sectors:
                for chdSector in hunk.sectors:
                    cdSector = CDSector(chdSector, index)
                    self.allSectors.append(cdSector)
                    index += 1

class CDSector:
    def __init__(self, chdSector, index):
        self._debug_chdSector = chdSector

        if not IGNORE_SUBCODE:
            self.rawSubcode = chdSector["subcode"]
        rawSector = chdSector["sector"]
        if not chdSector["hasEcc"] and rawSector[:12] != CD_SYNC_HEADER:
            self.kind = "rawAudio"
            self.data = rawSector
            self.sectors = index % 75
            self.seconds = (index // 75) % 60
            self.minutes = index // (75 * 60)



            # Unused fields
            self.mode = None
            self.crc32 = None
            self.ecc = None

        else:
            self.kind = "data"
            # First 12 bytes are sync pattern, ignore them.
            # Next three bytes are sector address
            self.minutes = fromBcd(rawSector[12])
            self.seconds = fromBcd(rawSector[13])
            self.sectors = fromBcd(rawSector[14])
            self.mode = rawSector[15]

            assert self.sectors == index % 75, (self.sectors, index, index % 75)
            assert self.seconds == (index // 75) % 60, (self.seconds, index, (index // 75) % 60)
            assert self.minutes == index // (75 * 60), (self.minutes, index, index // (75 * 60))
            #if self.sectors != index % 75:
            #    print(self.sectors, index, index % 75)
            #if self.seconds != (index // 75) % 60:
            #    print(self.seconds, index, (index // 75) % 60)
            #if self.minutes != index // (75 * 60):
            #    print(self.minutes, index, index // (75 * 60))

            if self.mode == 1:
                self.data = rawSector[16:16 + 2048]
                self.crc32 = rawSector[16 + 2048:16 + 2048 + 4]
                # 8 bytes between crc and ecc are reserved
                self.ecc = rawSector[16 + 2048 + 4 + 8:]
            else:
                self.data = rawSector[16:]
                self.crc32 = None
                self.ecc = None

                
def imageToFile(image, f):
    sectorArray = []
    blobOffset = 0

    total = len(image.allSectors)

    # --- First pass: build metadata ---
    for i, sector in enumerate(image.allSectors):
        if i % 10000 == 0:
            print("metadata", i, "/", total)

        entry = {
            "dataOffset": blobOffset,
            "dataLength": len(sector.data),
            "minute": sector.minutes,
            "second": sector.seconds,
            "frame": sector.sectors,
        }

        blobOffset += len(sector.data)

        if sector.kind == "rawAudio":
            entry["mode"] = "AUDIO"
        else:
            entry["mode"] = "MODE" + str(sector.mode)

        sectorArray.append(entry)

    metadata_bytes = json.dumps(
        {"sectors": sectorArray},
        separators=(',', ':')
    ).encode("utf-8")

    header_size = 16  # two uint64 values
    blobStart = header_size + len(metadata_bytes)

    # Align to 8 bytes
    padding = (8 - (blobStart % 8)) % 8
    blobStart += padding

    f.write(struct.pack("QQ", blobStart, len(metadata_bytes)))
    f.write(metadata_bytes)
    f.write(bytes([0] * padding))

    for i, sector in enumerate(image.allSectors):
        if i % 10000 == 0:
            print("blob", i, "/", total)

        f.write(sector.data)


# --- main pipeline ---
def main():
    if len(sys.argv) < 2:
        print("Usage: python chd_to_dat.py <file.chd>")
        sys.exit(1)

    filename = sys.argv[1]

    if not filename.endswith(".chd"):
        print("Input must be a .chd file")
        sys.exit(1)

    print("Reading CHD...")
    with open(filename, "rb") as f:
        gameFile = f.read()

    gameChd = ChdFile(gameFile)   # <-- adjust if needed

    print("Decoding CD image...")
    gameCD = CDImage(gameChd)

    output_path = filename.replace(".chd", ".dat")
    print("Writing to:", output_path)

    with open(output_path, "wb") as f:
        imageToFile(gameCD, f)

    print("Done.")


if __name__ == "__main__":
    main()
