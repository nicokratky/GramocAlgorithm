

import org.json.JSONObject;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashMap;

public class Client {

    private static String SERVER_IP = null;
    private static int SERVER_PORT = 0;

    private static final int BUFSIZE = 4096;
    private static final String PACK_FORMAT = ">IHH";
    private static final int METADATA_LENGTH = 8;

    public enum DATA_TYPES {
        NOT_FOUND(-1),
        HASH_MAP(1),
        STRING(2),
        INT(3),
        FLOAT(4),
        LIST_INT(5),
        LIST_FLOAT(6);

        public final int value;

        public static final HashMap<Integer, DATA_TYPES> lookup = new HashMap<>();

        static {
            for (DATA_TYPES d: DATA_TYPES.values()) {
                lookup.put(d.value, d);
            }
        }

        DATA_TYPES(int value) {
            this.value = value;
        }

        public static DATA_TYPES getDataType(int data_type) {
            return lookup.get(data_type);
        }
    }

    public enum CHANNELS {
        COM(1),
        DAT(2);

        public final int value;

        public static final HashMap<Integer, CHANNELS> lookup = new HashMap<>();

        static {
            for (CHANNELS c : CHANNELS.values()) {
                lookup.put(c.value, c);
            }
        }

        CHANNELS(int value) {
            this.value = value;
        }

        public static CHANNELS getChannel(int code) {
            return lookup.get(code);
        }
    }

    public enum COMMAND {
        CONNECT("CNCT"),
        CLOSE("CLS");

        private final String value;

        COMMAND(String value) {
            this.value = value;
        }
    }

    private Socket socket;

    public Client() {
        this("localhost", 1337);
    }

    public Client(String server_ip, int server_port) {

        SERVER_IP = server_ip;
        SERVER_PORT = server_port;

        try {
            socket = open_socket(SERVER_IP, SERVER_PORT, 5);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void close() {
        try {
            socket.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    /* TODO
    public void send(HashMap data) {

    }*/

    public void send(String data) {
        send(data.getBytes(StandardCharsets.UTF_8), DATA_TYPES.STRING.value);
    }

    public void send(int data) {
        send(String.valueOf(data).getBytes(StandardCharsets.UTF_8), DATA_TYPES.INT.value);
    }

    public void send(double data) {
        send(String.valueOf(data).getBytes(StandardCharsets.UTF_8), DATA_TYPES.FLOAT.value);
    }

    public void send(int[] data) {
        send(Arrays.toString(data).getBytes(StandardCharsets.UTF_8), DATA_TYPES.LIST_INT.value);
    }

    public void send(double[] data) {
        send(Arrays.toString(data).getBytes(StandardCharsets.UTF_8), DATA_TYPES.LIST_FLOAT.value);
    }

    private void send(byte[] data, int data_type) {
        try {
            OutputStream output = socket.getOutputStream();

            int channel = CHANNELS.COM.value;

            byte[] packed_data = pack_data(data, data_type, channel);

            /*int sent = 0;

            while(sent < packed_data.length) {
                output.write(packed_data, sent, Math.min(packed_data.length-sent, BUFSIZE));
                sent += Math.min((packed_data.length-sent), BUFSIZE);
            }*/

            output.write(packed_data);
        } catch (IOException e) {
            e.printStackTrace();
        }

        System.out.println("Successfully sent message!");
    }

    private byte[] pack_data(byte[] data, int data_type, int channel) {
        Struct s = new Struct();

        long[] metadata = new long[]{data.length, data_type, channel};

        byte[] meta;
        try {
            meta = s.pack(PACK_FORMAT, metadata);
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }

        byte[] packed = new byte[meta.length + data.length];
        System.arraycopy(meta, 0, packed, 0, meta.length);
        System.arraycopy(data, 0, packed, meta.length, data.length);

        return packed;
    }

    public Readout recv() {
        try {
            InputStream input = socket.getInputStream();

            long[] header = get_header(input);

            if (header == null) {
                return null;
            }

            long msg_len = header[0];
            long data_type = header[1];
            long channel = header[2];

            byte[] data = read_bytes(input, (int) msg_len);

            Object converted_data = convert_data(data, (int) data_type);

            Readout r = new Readout(CHANNELS.getChannel((int) channel), DATA_TYPES.getDataType((int) data_type),
                    converted_data);

            return r;

        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    private byte[] read_bytes(InputStream input, int bytes) {
        byte[] b = new byte[bytes];

        try {
            int read = input.read(b, 0, bytes);

            while (read < bytes) {
                read = input.read(b, read, Math.min(bytes-read, BUFSIZE));
            }

            return b;
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    private long[] get_header(InputStream input) {
        byte[] header = read_bytes(input, METADATA_LENGTH);

        Struct s = new Struct();

        try {
            return s.unpack(PACK_FORMAT, header);
        } catch (Exception e) {
            e.printStackTrace();
        }
        return null;

    }

    private Object convert_data(byte[] data, int data_type) {

        DATA_TYPES d = DATA_TYPES.getDataType(data_type);

        String arr;

        switch (d) {
            case HASH_MAP:
                return new JSONObject(new String(data));
            case STRING:
                return new String(data);
            case INT:
                return Integer.parseInt(new String(data));
            case FLOAT:
                return Float.parseFloat(new String(data));
            case LIST_INT:
                arr = new String(data);
                return Arrays.stream(arr.substring(1, arr.length()-1).split(","))
                        .map(String::trim).mapToInt(Integer::parseInt).toArray();
            case LIST_FLOAT:
                arr = new String(data);
                return Arrays.stream(arr.substring(1, arr.length()-1).split(","))
                        .map(String::trim).mapToDouble(Double::parseDouble).toArray();
            case NOT_FOUND:
                break;
        }

        return null;
    }

    private static Socket open_socket(String ip, int port, int timeout) throws Exception {
        Socket s;

        InetAddress inet_address = InetAddress.getByName(SERVER_IP);
        SocketAddress socket_address = new InetSocketAddress(inet_address, SERVER_PORT);

        s = new Socket();

        int timeout_ms = timeout * 1000;

        s.connect(socket_address, timeout_ms);

        return s;
    }

    public void connect() {
        while (true) {
            send(COMMAND.CONNECT.value);
            System.out.println("Sent handshake command!");

            Readout r = recv();

            if (r != null
                    && r.getChannel() == CHANNELS.COM
                    && r.getDataType() == DATA_TYPES.STRING
                    && String.valueOf(r.getData()).equals(COMMAND.CONNECT.value)) {
                System.out.println("Shook hands, connected!");
                break;
            }

            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }

    public static void main(String[] args) {

        Client c = new Client();

        c.connect();


        JSONObject j = (JSONObject) c.recv().getData();

        System.out.println(j.get("z"));
    }
}