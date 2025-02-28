# Stage 1: Build the Swift app with Swift 6.0
FROM swift:6.0-jammy AS builder

# Copy only the swift directory into the container at /swift
COPY ./server /server

# Set the working directory to /swift/web
WORKDIR /server/web

# Build your Swift app from /swift/web
RUN swift build -c release
# Greatly reduces the size of the binary by stripping debug symbols
RUN strip /server/web/.build/release/boss
# Generate list of dependencies required to run boss
#RUN ldd -r /swift/web/.build/release/boss | grep -o '/[^ ]*\.so[^ ]*' | sort -u > /server/deps.txt

# Stage 2: Runtime image with Debian Slim (glibc-based)
FROM debian:bullseye-slim

# Install basic dependencies, Python3, and Swift runtime essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-minimal libatomic1 libcurl4 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Copy Swift runtime libraries from the builder

# Copies over all swift binaries
#COPY --from=builder /usr/lib/swift/linux /usr/lib/swift/linux

# Copy specific files required by boss
COPY --from=builder /usr/lib/swift/linux/libswiftCore.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswift_Concurrency.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswift_StringProcessing.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswift_RegexParser.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswiftGlibc.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libBlocksRuntime.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libdispatch.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswiftDispatch.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libFoundation.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libFoundationEssentials.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libFoundationInternationalization.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/lib_FoundationICU.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswiftSynchronization.so /usr/lib/swift/linux/

# Copy only the dependencies (hopefully including transitive deps) required
# by boss.
#COPY --from=builder /server/deps.txt /tmp/deps.txt
#RUN cat /tmp/deps.txt | xargs -I {} cp --parents {} / --from=builder && rm /tmp/deps.txt
#RUN cat /tmp/deps.txt | xargs -I {} cp --parents {} / --from=builder

# Copy the compiled Swift binary from the correct build path
COPY --from=builder /server/web/.build/release/boss /usr/local/bin/boss

# Set the working directory
WORKDIR /app

# Ensure the binary can find the Swift libs
ENV LD_LIBRARY_PATH=/usr/lib/swift/linux:$LD_LIBRARY_PATH

# Command to run your app (temporary, for testing)
#CMD ["/usr/local/bin/boss"]
