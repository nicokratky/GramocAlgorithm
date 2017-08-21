

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
        SYNCHRONIZE("SYN"),
        ACKNOWLEDGE("ACK"),
        DISCONNECT("FIN"),
        START_DATA("STD"),
        STOP_DATA("SPD");

        public final String value;

        COMMAND(String value) {
            this.value = value;
        }
    }

    private Socket socket;

    public Client() throws UnknownHostException {
        this("localhost", 1337);
    }

    public Client(String server_ip, int server_port) throws UnknownHostException {

        SERVER_IP = server_ip;
        SERVER_PORT = server_port;

        socket = open_socket(SERVER_IP, SERVER_PORT, 5);

    }

    public void close() {
        System.out.println("Closing connection");
        send(COMMAND.STOP_DATA.value);
        send(COMMAND.DISCONNECT.value);

        Readout r;
        boolean closed = false;

        while(!closed) {
            r = recv();
            if (r != null
                    && r.getChannel() == CHANNELS.COM
                    && r.getDataType() == DATA_TYPES.STRING
                    && String.valueOf(r.getData()).equals(COMMAND.DISCONNECT.value)) {
                try {
                    socket.close();
                    closed = true;
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
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

            int sent = 0;

            while(sent < packed_data.length) {
                output.write(packed_data, sent, Math.min(packed_data.length-sent, BUFSIZE));
                sent += Math.min((packed_data.length-sent), BUFSIZE);
            }
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

        String s = new String(data);
        String[] sarr;

        switch (d) {
            case HASH_MAP:
                return new JSONObject(s);
            case STRING:
                return s;
            case INT:
                return Integer.parseInt(s);
            case FLOAT:
                return Float.parseFloat(s);
            case LIST_INT:
                sarr = s.substring(1, s.length() - 1).split(",");
                int[] iarr = new int[sarr.length];
                for(int i = 0; i < sarr.length; i++) {
                    iarr[i] = Integer.parseInt(sarr[i].trim());
                }
                return iarr;
            case LIST_FLOAT:
                sarr = s.substring(1, s.length() - 1).split(",");
                double[] darr = new double[sarr.length];
                for(int i = 0; i < sarr.length; i++) {
                    darr[i] = Double.parseDouble(sarr[i].trim());
                }
                return darr;
            case NOT_FOUND:
                break;
        }

        return null;
    }

    private static Socket open_socket(String ip, int port, int timeout) throws UnknownHostException {
        Socket s = null;

        InetAddress inet_address = InetAddress.getByName(SERVER_IP);

        try {
            s = new Socket(inet_address, SERVER_PORT);
        }
        catch (IOException e) {
            e.printStackTrace();
        }

        return s;
    }

    public boolean connect() {
        System.out.println("Shaking hands");
        send(COMMAND.SYNCHRONIZE.value);

        Readout r = recv();

        if (r != null
                && r.getChannel() == CHANNELS.COM
                && r.getDataType() == DATA_TYPES.STRING
                && String.valueOf(r.getData()).equals(COMMAND.ACKNOWLEDGE.value)) {
            System.out.println("Received SYN/ACK");
            send(COMMAND.ACKNOWLEDGE.value);
            return true;
        }

        return false;
    }

    public Socket getSocket() {
        return socket;
    }

    public static void main(String[] args) {

        Client c = null;
        try {
            c = new Client();
        } catch (UnknownHostException e) {
            e.printStackTrace();
        }

        while (!c.connect());

        c.send("Hallo Server");

        c.close();
    }
}