import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.util.Hashtable;


public class TranslitSents {

	/**
	 * @param args
	 */
	
	private String line;
	private  Hashtable<String, String>  sien_map;
	
	TranslitSents(){
		this.line = "";
		this.sien_map = new Hashtable<String, String>();
	}
	
	public Hashtable word_map(String mapName) throws IOException{
		
		// Get char types for all phones
	    FileInputStream localFileInputStream = new FileInputStream(mapName);
	    BufferedReader localBufferedReader = new BufferedReader(new InputStreamReader(localFileInputStream, "UTF8"));
	    int index = 0;
	    for (;;)
	    {
	    	index = index+1;
	      this.line = localBufferedReader.readLine();
	      if (this.line == null) {
	        break;
	      }
	      this.sien_map.put(this.line.substring(0, this.line.indexOf("\t")), this.line.substring(this.line.indexOf("\t")+1, this.line.length()));
	    }
	    localBufferedReader.close();
	    System.out.println(this.sien_map.size());
	    return this.sien_map;
	}
	
	public String translit(String word){
		
		String trans = "";
		//System.out.println("word = " + word);
		System.out.println(this.sien_map.containsKey(word));
		if(this.sien_map.containsKey(word)){
			trans = this.sien_map.get(word);
			//System.out.println("trans = " + trans);
		}
		else
			trans = "null";
		
		return trans;
	}
	
	public static void main(String[] args) throws IOException {
		
		TranslitSents ts = new TranslitSents();
		String mapName = "F002_SiEnMap.txt";
		Hashtable<String, String> map = ts.word_map(mapName);
		
		FileInputStream localFileInputStream = new FileInputStream(new File("F002_Prompts.txt"));
		BufferedReader localBufferedReader = new BufferedReader(new InputStreamReader(localFileInputStream, "UTF8"));
		
		FileOutputStream localFileOutputStream = new FileOutputStream(new File("F002_Prompts_Entrans.txt"));
	    BufferedWriter localBufferedWriter = new BufferedWriter(new OutputStreamWriter(localFileOutputStream));
	      
	
		String line = localBufferedReader.readLine();
		while(line != null){
			String[] words = line.trim().split(" ");
			String trans = "";
			String sent = "";
			for(int i=0; i< words.length; i++){
				trans = ts.translit(words[i]);
				//System.out.println("TRANS = " + trans);
				if(sent.equals("")){
					sent = sent.concat(trans);
				}
				else
					sent = sent.concat(" ").concat(trans);
			}
			
			localBufferedWriter.write(sent.concat("\n"));
			line = localBufferedReader.readLine();
		}
		
		localBufferedWriter.close();
		localBufferedReader.close();
	}

}
