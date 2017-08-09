

public class Readout {

    private Client.CHANNELS channel;
    private Client.DATA_TYPES data_type;
    private Object data;

    public Readout(Client.CHANNELS channel, Client.DATA_TYPES data_type, Object data) {
        this.channel = channel;
        this.data_type = data_type;
        this.data = data;
    }

    public Client.CHANNELS getChannel() {
        return channel;
    }

    public Client.DATA_TYPES getDataType() {
        return data_type;
    }

    public Object getData() {
        return data;
    }

    @Override
    public String toString() {
        return "Channel: " + channel + "\n"
                + "Data Type: " + data_type + "\n"
                + "Data : " + data;
    }
}
